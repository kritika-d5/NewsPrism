from typing import Dict, List, Optional
import numpy as np
from transformers import pipeline
import spacy
from app.core.config import settings


class BiasAnalyzer:
    def __init__(self):
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            device=-1
        )
        
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("spaCy model not found. Run: python -m spacy download en_core_web_sm")
            self.nlp = None
        
        self.loaded_patterns = {
            "emotive": ["shocking", "devastating", "tragic", "outrageous", "scandalous"],
            "prescriptive": ["must", "should", "ought", "need to"],
            "hedging": ["perhaps", "maybe", "possibly", "might", "could"],
            "intensifiers": ["very", "extremely", "incredibly", "absolutely"]
        }
    
    def analyze_article(self, text: str) -> Dict:
        tone_score = self._analyze_tone(text)
        lexical_bias = self._analyze_lexical_bias(text)
        subjectivity = self._analyze_subjectivity(text)
        
        return {
            "tone_score": tone_score,
            "lexical_bias_score": lexical_bias,
            "subjectivity_score": subjectivity,
            "loaded_phrases": self._extract_loaded_phrases(text)
        }
    
    def _analyze_tone(self, text: str) -> float:
        sentences = text.split('.')[:10]
        
        if not sentences:
            return 0.0
        
        scores = []
        for sentence in sentences:
            if len(sentence.strip()) < 10:
                continue
            
            try:
                result = self.sentiment_pipeline(sentence[:512])[0]
                label = result['label'].lower()
                score = result['score']
                
                if 'positive' in label:
                    scores.append(score)
                elif 'negative' in label:
                    scores.append(-score)
                else:
                    scores.append(0)
            except:
                continue
        
        if not scores:
            return 0.0
        
        return np.mean(scores)
    
    def _analyze_lexical_bias(self, text: str) -> float:
        if not self.nlp:
            return self._simple_lexical_bias(text)
        
        doc = self.nlp(text.lower())
        total_tokens = len([t for t in doc if t.is_alpha])
        
        if total_tokens == 0:
            return 0.0
        
        loaded_count = 0
        for pattern_type, words in self.loaded_patterns.items():
            for word in words:
                loaded_count += text.lower().count(word)
        
        adj_adv_count = len([t for t in doc if t.pos_ in ['ADJ', 'ADV']])
        lexical_score = min(
            (loaded_count * 2 + adj_adv_count * 0.1) / total_tokens,
            1.0
        )
        
        return lexical_score
    
    def _simple_lexical_bias(self, text: str) -> float:
        words = text.lower().split()
        total_words = len(words)
        
        if total_words == 0:
            return 0.0
        
        loaded_count = 0
        for pattern_type, pattern_words in self.loaded_patterns.items():
            for word in pattern_words:
                loaded_count += words.count(word)
        
        return min(loaded_count / total_words, 1.0)
    
    def _analyze_subjectivity(self, text: str) -> float:
        opinion_indicators = [
            "i think", "i believe", "in my opinion", "seems", "appears",
            "likely", "probably", "suggests", "indicates"
        ]
        
        text_lower = text.lower()
        indicator_count = sum(1 for indicator in opinion_indicators if indicator in text_lower)
        sentences = text.split('.')
        return min(indicator_count / max(len(sentences), 1), 1.0)
    
    def _extract_loaded_phrases(self, text: str, max_phrases: int = 8) -> List[Dict]:
        phrases = []
        
        if not self.nlp:
            return phrases
        
        doc = self.nlp(text)
        
        for sent in doc.sents:
            sent_text = sent.text.lower()
            
            for pattern_type, words in self.loaded_patterns.items():
                for word in words:
                    if word in sent_text:
                        phrases.append({
                            "phrase": sent.text[:100],
                            "type": pattern_type,
                            "reason": f"Contains {pattern_type} language"
                        })
                        
                        if len(phrases) >= max_phrases:
                            return phrases
        
        return phrases[:max_phrases]
    
    def compute_bias_index(
        self,
        tone_score: float,
        lexical_bias: float,
        omission_score: float,
        consistency_score: float,
        cluster_mean_tone: float,
        fact_emotion: float = 0.0,
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        if weights is None:
            weights = {
                "tone": settings.BIAS_WEIGHT_TONE,
                "lexical": settings.BIAS_WEIGHT_LEXICAL,
                "omission": settings.BIAS_WEIGHT_OMISSION,
                "consistency": settings.BIAS_WEIGHT_CONSISTENCY,
            }

        weight_sum = sum(weights.values()) or 1.0
        weights = {k: v / weight_sum for k, v in weights.items()}

        tone_deviation = abs(tone_score - cluster_mean_tone) / 2.0
        tone_deviation = max(0.0, min(1.0, tone_deviation))

        dissonance_penalty = 0.0
        if fact_emotion != 0.0:
            emotion_delta_norm = abs(tone_score - fact_emotion) / 2.0
            if emotion_delta_norm > 0.25:
                dissonance_penalty = min(0.3, emotion_delta_norm * 0.3)

        bias_mag = (
            weights["tone"] * tone_deviation
            + weights["lexical"] * lexical_bias
            + weights["omission"] * omission_score
            + weights["consistency"] * consistency_score
            + dissonance_penalty
        )

        bias_index = min(100.0, 100.0 * (bias_mag / 1.3))
        return bias_index
    
    def compute_transparency_score(
        self,
        omission_score: float,
        consistency_score: float,
        lexical_bias: float,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        if weights is None:
            weights = {"lexical": 0.2, "omission": 0.4, "consistency": 0.4}

        lex_w = weights.get("lexical", 0.0)
        om_w = weights.get("omission", 0.0)
        cons_w = weights.get("consistency", 0.0)
        w_sum = (lex_w + om_w + cons_w) or 1.0
        lex_w /= w_sum
        om_w /= w_sum
        cons_w /= w_sum

        transparency = 100.0 * (1.0 - (om_w * omission_score + cons_w * consistency_score + lex_w * lexical_bias))
        return max(0.0, min(100.0, transparency))

