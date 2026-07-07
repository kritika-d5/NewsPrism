from typing import List, Dict, Optional
import spacy
import httpx
import numpy as np
from app.core.config import settings
from app.services.embeddings.embedding_service import EmbeddingService


class FactExtractor:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("spaCy model not found. Run: python -m spacy download en_core_web_sm")
            self.nlp = None
        
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_api_url = settings.GROQ_API_URL
        self.embedding_service = EmbeddingService()
    
    async def extract_facts_from_articles(
        self,
        articles: List[Dict],
        query: Optional[str] = None
    ) -> List[Dict]:
        candidate_facts = self._extract_candidate_facts(articles)
        print(f"[fact_extractor] articles={len(articles)} candidates={len(candidate_facts)}")

        if query:
            candidate_facts = await self._filter_by_semantic_relevance(candidate_facts, query)
            print(f"[fact_extractor] after semantic filter: {len(candidate_facts)}")

        verified_facts = await self._verify_facts_with_llm(candidate_facts, articles)
        print(f"[fact_extractor] verified: {len(verified_facts)}")
        return verified_facts
    
    def _extract_candidate_facts(self, articles: List[Dict]) -> List[Dict]:
        if not self.nlp:
            return self._simple_fact_extraction(articles)
        
        facts = []
        
        for article in articles:
            text = article.get("text", "")
            doc = self.nlp(text)
            
            entities = {}
            for ent in doc.ents:
                if ent.label_ in ["PERSON", "ORG", "GPE", "EVENT", "DATE"]:
                    if ent.label_ not in entities:
                        entities[ent.label_] = []
                    entities[ent.label_].append(ent.text)
            
            for sent in doc.sents:
                sent_text = sent.text.strip()
                word_count = len(sent_text.split())
                
                if word_count < 10:
                    continue
                
                has_entity = any(ent in sent.text for ents in entities.values() for ent in ents)
                if has_entity and len(sent_text) > 20:
                    if not FactExtractor._is_noise(sent_text):
                        facts.append({
                            "fact": sent_text,
                            "source_url": article.get("url"),
                            "source_name": article.get("source"),
                            "entities": {k: list(set(v)) for k, v in entities.items()}
                        })
        
        return facts[:50]
    
    @staticmethod
    def _is_noise(text: str) -> bool:
        text_lower = text.lower()
        noise_indicators = [
            'photo credit', 'representative image', 'image:', 'photo:',
            'click here', 'read more', 'subscribe', 'follow us', 'share this',
            'advertisement', 'ad:', 'sponsored', 'breaking news', 'live:',
            'none...', 'loading...', 'cookie', 'privacy policy', 'terms of service'
        ]
        return any(indicator in text_lower for indicator in noise_indicators)
    
    def _simple_fact_extraction(self, articles: List[Dict]) -> List[Dict]:
        facts = []
        
        for article in articles:
            text = article.get("text", "")
            sentences = text.split('.')
            
            for sent in sentences:
                sent_text = sent.strip()
                word_count = len(sent_text.split())
                
                if word_count < 10 or len(sent_text) < 30:
                    continue
                
                if FactExtractor._is_noise(sent_text):
                    continue
                
                if any(c.isdigit() for c in sent) or any(c.isupper() for c in sent[:10]):
                    facts.append({
                        "fact": sent_text,
                        "source_url": article.get("url"),
                        "source_name": article.get("source"),
                        "entities": {}
                    })
        
        return facts[:50]
    
    async def _filter_by_semantic_relevance(
        self,
        candidate_facts: List[Dict],
        query: str,
        threshold: float = 0.32,
        min_keep: int = 10,
        max_keep: int = 30,
    ) -> List[Dict]:
        """Keep the facts most semantically related to the query.

        Short queries vs. full sentences rarely exceed ~0.5 cosine similarity
        with MiniLM, so a hard high threshold silently discards everything.
        Instead: rank all candidates by similarity, keep those above a modest
        threshold, and always keep at least ``min_keep`` so the fact-checking
        stage is never starved.
        """
        if not candidate_facts or not query:
            return candidate_facts

        texts = [f.get("fact", "") for f in candidate_facts]
        query_embedding = np.array(self.embedding_service.embed_text(query))
        fact_embeddings = np.array(self.embedding_service.embed_batch(texts))

        # Embeddings are normalized by the service; dot product = cosine sim.
        sims = fact_embeddings @ query_embedding

        ranked = sorted(zip(candidate_facts, sims), key=lambda x: x[1], reverse=True)
        above = [f for f, s in ranked if s >= threshold]

        if len(above) >= min_keep:
            return above[:max_keep]
        return [f for f, _ in ranked[:min_keep]]
    
    async def _verify_facts_with_llm(
        self,
        candidate_facts: List[Dict],
        articles: List[Dict]
    ) -> List[Dict]:
        verified_facts = []
        fact_groups = self._group_similar_facts(candidate_facts)
        
        for fact_group in fact_groups[:20]:
            prompt = self._create_verification_prompt(fact_group, articles)
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.groq_api_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.groq_api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a fact verification assistant. Analyze candidate facts and determine their status across sources."
                                },
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            "temperature": 0.1,
                            "max_tokens": 1000
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code != 200:
                        print(f"Groq API Error in Verification ({response.status_code}): {response.text}")
                        continue

                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    result = self._parse_verification_response(
                        content,
                        fact_group,
                        articles
                    )
                
                if result and result.get("status") != "rejected":
                    verified_facts.append(result)
            
            except Exception as e:
                print(f"Error in LLM verification: {str(e)}")
                if fact_group and not FactExtractor._is_noise(fact_group[0].get("fact", "")):
                    verified_facts.append({
                        "fact": fact_group[0].get("fact", ""),
                        "sources": [f.get("source_url", "") for f in fact_group],
                        "quotes": [f.get("fact", "") for f in fact_group[:2]],
                        "status": "unverified"
                    })
        
        return verified_facts
    
    def _group_similar_facts(self, facts: List[Dict]) -> List[List[Dict]]:
        groups = []
        used = set()
        
        for i, fact in enumerate(facts):
            if i in used:
                continue
            
            group = [fact]
            used.add(i)
            
            fact_keywords = set(self._extract_keywords(fact.get("fact", "")))
            
            for j, other_fact in enumerate(facts[i+1:], start=i+1):
                if j in used:
                    continue
                
                other_keywords = set(self._extract_keywords(other_fact.get("fact", "")))
                overlap = len(fact_keywords & other_keywords)
                if overlap >= 2:
                    group.append(other_fact)
                    used.add(j)
            
            groups.append(group)
        
        return groups
    
    def _extract_keywords(self, text: str) -> List[str]:
        words = text.lower().split()
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
        return [w.strip('.,!?;:') for w in words if w.lower() not in stop_words and len(w) > 3]
    
    def _create_verification_prompt(
        self,
        fact_group: List[Dict],
        articles: List[Dict]
    ) -> str:
        fact_text = fact_group[0].get("fact", "")
        
        sources_text = "\n".join([
            f"Source: {f.get('source_name', 'Unknown')} ({f.get('source_url', '')})\n"
            f"Excerpt: {f.get('fact', '')[:200]}\n"
            for f in fact_group[:5]
        ])
        
        prompt = f"""You are a fact verification assistant. Given a candidate fact and excerpts from multiple sources, FIRST determine if it is a substantive news claim.

REJECT if the candidate is:
- A photo credit, image caption, or image description
- A navigation link, site tagline, or UI element
- A breaking news alert or notification
- An advertisement or sponsored content
- A social media prompt (e.g., "Click here", "Share this")
- Metadata or boilerplate text

If it IS a substantive news claim, then determine:
1. (A) Supported - appears verbatim or clearly implied by at least one reliable source
2. (B) Contradicted - some sources claim the opposite
3. (C) Unverified - no sufficient evidence

Candidate fact: {fact_text}

Sources:
{sources_text}

Return your analysis in this format:
STATUS: [A/B/C/REJECTED]
JUSTIFICATION: [1-line explanation]
QUOTES: [up to 2 supporting quotes with source URLs, or N/A if REJECTED]
"""
        return prompt
    
    def _parse_verification_response(
        self,
        response: str,
        fact_group: List[Dict],
        articles: List[Dict]
    ) -> Dict:
        lines = response.split('\n')
        
        status = "unverified"
        justification = ""
        quotes = []
        
        for line in lines:
            if line.startswith("STATUS:"):
                status_part = line.split(":", 1)[1].strip().upper()
                if "REJECTED" in status_part or "reject" in status_part.lower():
                    return None
                elif "A" in status_part or "supported" in status_part.lower():
                    status = "supported"
                elif "B" in status_part or "contradicted" in status_part.lower():
                    status = "contradicted"
            elif line.startswith("JUSTIFICATION:"):
                justification = line.split(":", 1)[1].strip()
            elif line.startswith("QUOTES:"):
                quotes_text = line.split(":", 1)[1].strip()
                if quotes_text.upper() != "N/A":
                    quotes = [q.strip() for q in quotes_text.split('\n') if q.strip() and q.strip().upper() != "N/A"]
        
        if not quotes:
            quotes = [f.get("fact", "")[:100] for f in fact_group[:2]]
        
        sources = [f.get("source_url", "") for f in fact_group]
        
        return {
            "fact": fact_group[0].get("fact", ""),
            "sources": sources,
            "quotes": quotes,
            "status": status,
            "justification": justification
        }