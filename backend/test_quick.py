"""Quick test of non-BioBERT components."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

print("=" * 50)
print("QUICK COMPONENT TEST (no BioBERT)")
print("=" * 50)

# 1. OCR Space text processing
print("\n[1] OCR Space text processing...")
from services.ocr_space_service import build_ocr_result
sample = "Patient Name: Ahmed\nHemoglobin: 10.2\nGlucose: 250\nCreatinine: 2.1"
result = build_ocr_result(sample, "lab.jpg")
print("    OK - Dept:", result["department_name"])
print("    Summary:", result["summary"][:100])

# 2. OpenAI availability
print("\n[2] OpenAI availability...")
from services.openai_service import openai_unavailable_message, configured_model
unavail = openai_unavailable_message()
if unavail:
    print("    UNAVAILABLE:", unavail)
else:
    print("    AVAILABLE - model:", configured_model())

# 3. Rule validation
print("\n[3] Rule validation...")
from services.rule_validation_service import validate_medical_rules
rv = validate_medical_rules("Glucose 350. BP 180/120. warfarin aspirin.", {}, [])
print("    OK - status:", rv["status"], "| warnings:", len(rv["warnings"]))
for w in rv["warnings"][:3]:
    print("      -", w["severity"], ":", w["message"][:80])

# 4. NLP service
print("\n[4] NLP rule-based summary...")
from services.nlp_service import build_rule_based_summary
s = build_rule_based_summary("Hemoglobin 10.2. Glucose 250.", "lab")
print("    OK -", s[:120])

# 5. Database
print("\n[5] Database connection...")
try:
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1"))
        print("    OK - connected:", r.fetchone())
except Exception as ex:
    print("    FAILED:", ex)

print("\n" + "=" * 50)
print("QUICK TEST COMPLETE")
print("=" * 50)
