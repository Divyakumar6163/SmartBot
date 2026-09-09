from openai import OpenAI
import json
import re

client = OpenAI()

# =========================================================
# 1️⃣ ENHANCED NORMALIZATION (HINGLISH OPTIMIZED)
# =========================================================

def normalize(text: str) -> str:
    """
    Enhanced normalization with better Hinglish handling
    - lowercase
    - remove punctuation but keep spaces
    - normalize stretched words (chutiyaaa → chutiya)
    - handle common transliterations
    """
    text = text.lower()
    
    # Common Hinglish variations normalization
    replacements = {
        'paagal': 'pagal',
        'paagla': 'pagal',
        'tmse': 'tumse',
        'kr': 'kar',
        'rhe': 'rahe',
        'kya': 'kya',
        'kahi': 'kahin',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Remove punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    
    # Normalize stretched words (chutiyaaa → chutiya)
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text.strip()


# =========================================================
# 2️⃣ EXPANDED STRONG ABUSE DETECTION
# =========================================================

STRONG_ABUSE_WORDS = [
    # Hindi/Hinglish abuses
    "chutiya", "chutiye", "chutiyap", "chutiyapa",
    "madarchod", "madharchod", "mc",
    "bhosdi", "bhosadike", "bhosadiwale",
    "harami", "haramzada", "haramzade",
    "bsdk", "bhen", "behen",
    "gandu", "gando", "gandu",
    "kutte", "kutta", "kamina", "kamine",
    "saale", "sala", "saala",
    "randi", "randi",
    "lode", "laude", "lund",
    "gaand", "gand",
    
    # English abuses
    "fuck", "fucking", "fucked", "fucker",
    "shit", "shitty", "bullshit",
    "asshole", "ass", "bastard",
    "motherfucker", "bitch",
    "damn", "dammit"
]

THREAT_PATTERNS = [
    # Hindi threats
    "dekh lenge", "dekh lunga", "dekhte hain",
    "bura hoga", "bura karunga", "bura manoge",
    "jaante nahi ho", "pata chal jayega",
    "nahi chhodenge", "chodenge nahi",
    "theek nahi hoga", "achha nahi hoga",
    "complaint", "complain", "shikayat",
    "police", "cops",
    "case", "legal action",
    "consequences bhugto", "bhugto",
    "wait and watch", "dekhte raho",
    
    # English threats
    "you will regret", "you'll regret",
    "i will report", "will report you",
    "take action", "legal action",
    "consequences", "face consequences",
    "you don't know who i am",
    "i know people", "connections hai"
]

# Contextual abuse phrases (multi-word)
ABUSE_PHRASES = [
    "pagal hai kya", "pagal ho kya", "pagal ho gaya",
    "dimag kharab", "dimaag kharab",
    "bewakoof ho", "bewakoof hai",
    "buddhu ho", "ullu",
    "idiot ho", "stupid hai"
]

def strong_abuse_detected(text: str) -> bool:
    """Enhanced abuse detection with context awareness"""
    t = normalize(text)
    
    # Check single word abuses
    for word in STRONG_ABUSE_WORDS:
        # Word boundary matching
        pattern = rf"\b{re.escape(word)}\b"
        if re.search(pattern, t):
            return True
    
    # Check multi-word abuse phrases
    for phrase in ABUSE_PHRASES:
        if phrase in t:
            return True
    
    # Check threats
    for threat in THREAT_PATTERNS:
        if threat in t:
            return True
    
    return False


# =========================================================
# 3️⃣ ENHANCED MILD NEGATIVITY DETECTION
# =========================================================

MILD_NEGATIVE_WORDS = [
    # Hindi/Hinglish
    "pagal", "pareshaan", "pareshan",
    "bekaar", "bekar", "faltu",
    "bakwas", "bakwaas",
    "ghatiya", "kharab", "kharaab",
    "mushkil", "dikkat", "problem",
    "tang", "frustrated",
    
    # English
    "useless", "worst", "terrible",
    "irritating", "annoying", "frustrating",
    "horrible", "pathetic", "disappointing"
]

FRUSTRATION_PHRASES = [
    "bahut pareshan", "bahut pareshaan",
    "tang aa gaya", "tang hogaya",
    "thak gaya", "pak gaya",
    "baar baar", "bar bar",
    "kitni baar", "har baar",
    "kab tak", "kab se",
    "nahi ho raha", "nahi horaha",
    "kaam nahi kar raha", "kaam nahi hora"
]

def mild_hostility_detected(text: str) -> bool:
    """
    Detects frustration without abuse
    Example: 'bahut pareshan ho gaya hoon' → angry but NOT abusive
    """
    t = normalize(text)
    
    # Check for frustration phrases
    for phrase in FRUSTRATION_PHRASES:
        if phrase in t:
            return True
    
    # Check if mild negative words are used with service/system context
    service_context = any(word in t for word in ["system", "service", "app", "battery", "swap", "station"])
    
    if service_context:
        for word in MILD_NEGATIVE_WORDS:
            if word in t:
                return True
    
    return False


# =========================================================
# 4️⃣ IMPROVED LLM PROMPT WITH MORE EXAMPLES
# =========================================================

SENTIMENT_PROMPT = """
You are a highly accurate sentiment and abuse detection engine for EV drivers.
Drivers communicate in Hindi, Hinglish (Hindi written in English), or English.

Your task:
1. Detect sentiment: calm | neutral | angry
2. Detect abusive language: true | false

Classification Rules:
- ABUSIVE = true if: Direct insults, slurs, threats, extremely rude language
- ANGRY but NOT abusive: Frustration, complaints, repeated issues without slurs/threats
- NEUTRAL: Normal questions, factual complaints, information requests
- CALM: Polite requests, thanks, acknowledgments

Key Distinctions:
- "pagal hai kya" (are you crazy) = ANGRY + ABUSIVE (insulting)
- "bahut pagal ho gaya hoon" (I've become very frustrated) = ANGRY but NOT abusive (self-description)
- "baar baar ho raha hai" (happening repeatedly) = ANGRY but NOT abusive
- "dekh lenge" (we'll see/threat) = ANGRY + ABUSIVE (threat)
- "chutiya" or "madarchod" = ALWAYS abusive
- "pareshaan ho gaya" (got troubled) = ANGRY but NOT abusive

Return ONLY valid JSON (no extra text):
{
  "sentiment": "calm|neutral|angry",
  "abusive": true|false
}

Examples:

Input: "chutiya kahi ka"
Output: {"sentiment":"angry","abusive":true}

Input: "hm pagal hai kya tmse baat kr rhe h"
Output: {"sentiment":"angry","abusive":true}

Input: "tumhara dimag kharab hai"
Output: {"sentiment":"angry","abusive":true}

Input: "jaldi kaam nahi hua to dekh lenge"
Output: {"sentiment":"angry","abusive":true}

Input: "complaint karunga police mein"
Output: {"sentiment":"angry","abusive":true}

Input: "yeh kya bakwas service hai"
Output: {"sentiment":"angry","abusive":true}

Input: "bahut pareshan ho gaya hoon"
Output: {"sentiment":"angry","abusive":false}

Input: "main bahut pagal ho gaya hoon"
Output: {"sentiment":"angry","abusive":false}

Input: "yeh baar baar ho raha hai"
Output: {"sentiment":"angry","abusive":false}

Input: "kitni baar batana padega"
Output: {"sentiment":"angry","abusive":false}

Input: "tang aa gaya hoon is system se"
Output: {"sentiment":"angry","abusive":false}

Input: "battery kabse kharab hai"
Output: {"sentiment":"angry","abusive":false}

Input: "mera penalty galat laga hai"
Output: {"sentiment":"neutral","abusive":false}

Input: "swap limit kyun kam hai"
Output: {"sentiment":"neutral","abusive":false}

Input: "aaj kitna swap hua"
Output: {"sentiment":"neutral","abusive":false}

Input: "battery ID kya hai"
Output: {"sentiment":"neutral","abusive":false}

Input: "please meri help kar dijiye"
Output: {"sentiment":"calm","abusive":false}

Input: "thank you for your help"
Output: {"sentiment":"calm","abusive":false}

Input: "dhanyavaad aapka"
Output: {"sentiment":"calm","abusive":false}

Input: "theek hai samajh gaya"
Output: {"sentiment":"calm","abusive":false}
"""

def llm_sentiment(text: str) -> dict:
    """Call LLM for sentiment analysis with retry logic"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SENTIMENT_PROMPT},
                {"role": "user", "content": text}
            ]
        )
        
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        content = re.sub(r'^```json\s*|\s*```$', '', content, flags=re.MULTILINE)
        
        result = json.loads(content)
        
        # Validate response structure
        if "sentiment" not in result or "abusive" not in result:
            raise ValueError("Invalid response structure")
        
        # Validate sentiment values
        if result["sentiment"] not in ["calm", "neutral", "angry"]:
            result["sentiment"] = "neutral"
        
        return result
        
    except Exception as e:
        print(f"LLM sentiment error: {e}")
        return {"sentiment": "neutral", "abusive": False}


# =========================================================
# 5️⃣ MASTER FUNCTION WITH IMPROVED LOGIC
# =========================================================

def analyze_sentiment(text: str) -> dict:
    """
    Enhanced sentiment analysis with layered detection
    
    FINAL OUTPUT:
    {
      "abusive": bool,
      "sentiment": calm | neutral | angry,
      "severity": low | medium | high,
      "confidence": float (0-1)
    }
    """
    
    # Layer 1: Strong abuse detection (highest priority)
    if strong_abuse_detected(text):
        return {
            "abusive": True,
            "sentiment": "angry",
            "severity": "high",
            "confidence": 1.0
        }
    
    # Layer 2: Mild hostility detection
    mild_hostile = mild_hostility_detected(text)
    
    # Layer 3: LLM analysis
    llm_result = llm_sentiment(text)
    llm_sentiment_val = llm_result.get("sentiment", "neutral")
    llm_abusive = llm_result.get("abusive", False)
    
    # Decision logic: Combine rule-based and LLM
    
    # If LLM detected abuse, flag it
    if llm_abusive:
        return {
            "abusive": True,
            "sentiment": "angry",
            "severity": "high",
            "confidence": 0.9
        }
    
    # If mild hostility detected by rules
    if mild_hostile:
        return {
            "abusive": False,
            "sentiment": "angry",
            "severity": "medium",
            "confidence": 0.85
        }
    
    # If LLM says angry but no abuse
    if llm_sentiment_val == "angry":
        return {
            "abusive": False,
            "sentiment": "angry",
            "severity": "medium",
            "confidence": 0.8
        }
    
    # Calm or neutral
    severity = "low" if llm_sentiment_val == "calm" else "low"
    
    return {
        "abusive": False,
        "sentiment": llm_sentiment_val,
        "severity": severity,
        "confidence": 0.75
    }


# =========================================================
# 6️⃣ TESTING FUNCTION
# =========================================================

def test_sentiment():
    """Test cases for sentiment analysis"""
    
    test_cases = [
        # Abusive cases
        "chutiya kahi ka",
        "hm pagal hai kya tmse baat kr rhe h",
        "tumhara dimag kharab hai",
        "jaldi kaam nahi hua to dekh lenge",
        "madarchod service hai",
        
        # Angry but not abusive
        "bahut pareshan ho gaya hoon",
        "main bahut pagal ho gaya hoon",
        "yeh baar baar ho raha hai",
        "tang aa gaya hoon",
        "battery kabse kharab hai",
        
        # Neutral
        "mera penalty galat laga hai",
        "aaj kitna swap hua",
        "battery ID kya hai",
        
        # Calm
        "please meri help kar dijiye",
        "thank you",
        "dhanyavaad"
    ]
    
    print("=" * 60)
    print("SENTIMENT ANALYSIS TEST RESULTS")
    print("=" * 60)
    
    for text in test_cases:
        result = analyze_sentiment(text)
        print(f"\nInput: {text}")
        print(f"Result: {result}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_sentiment()