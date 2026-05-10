"""Troubleshooting script: tests each component of the OCR pipeline."""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))


def test_biobert():
    print("=== Testing BioBERT ===")
    try:
        from services.biobert_service import _load_pipeline
        ner = _load_pipeline()
        test = ner("Patient has diabetes and takes metformin 500mg")
        print(f"  BioBERT OK: found {len(test)} entities")
        for e in test[:3]:
            word = e.get("word", e.get("entity_group", "?"))
            score = e.get("score", 0)
            print(f"    - {word} (score={score:.2f})")
    except Exception as ex:
        print(f"  BioBERT FAILED: {ex}")


def test_biobert_fallback():
    print("\n=== Testing BioBERT Fallback (rule-based) ===")
    try:
        from services.biobert_service import fallback_entities
        entities = fallback_entities(
            "Patient has diabetes, fever, takes metformin and aspirin",
            {"glucose": "350", "hemoglobin": "8.2"},
        )
        print(f"  Fallback OK: found {len(entities)} entities")
        for e in entities[:5]:
            print(f"    - [{e['label']}] {e['text']} (conf={e['confidence']})")
    except Exception as ex:
        print(f"  Fallback FAILED: {ex}")


def test_rule_validation():
    print("\n=== Testing Rule Validation ===")
    try:
        from services.rule_validation_service import validate_medical_rules
        result = validate_medical_rules(
            "Glucose 350 mg/dL. Blood pressure 180/120. Patient takes warfarin and aspirin.",
            {},
            [],
        )
        status = result["status"]
        warnings = result["warnings"]
        print(f"  Rule validation OK: status={status}, warnings={len(warnings)}")
        for w in warnings[:4]:
            print(f"    - [{w['severity']}] {w['message']}")
    except Exception as ex:
        print(f"  Rule validation FAILED: {ex}")


def test_ocr_space_service():
    print("\n=== Testing OCR Space Service (text processing only) ===")
    try:
        from services.ocr_space_service import (
            clean_ocr_text,
            detect_department,
            detect_keywords,
            extract_structured_data,
            build_ocr_result,
        )
        sample = "Patient Name: John Doe\nAge: 45\nGender: Male\nHemoglobin: 10.2 g/dL\nGlucose: 250 mg/dL\nCreatinine: 2.1 mg/dL"
        cleaned = clean_ocr_text(sample)
        dept = detect_department(cleaned)
        keywords = detect_keywords(cleaned)
        structured = extract_structured_data(cleaned)
        result = build_ocr_result(sample, "lab_report.jpg")

        print(f"  Clean text OK: {len(cleaned)} chars")
        print(f"  Department: {dept}")
        print(f"  Keywords: {keywords}")
        print(f"  Structured fields: {list(structured.keys())}")
        print(f"  Build result keys: {list(result.keys())}")
        print(f"  Summary: {result.get('summary', 'NONE')[:120]}")
    except Exception as ex:
        print(f"  OCR Space Service FAILED: {ex}")


def test_ocr_space_api_key():
    print("\n=== Testing OCR Space API Key ===")
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).resolve().parent / ".env")
        load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

        api_key = os.getenv("OCR_SPACE_API_KEY", "").strip().strip('"').strip("'")
        if api_key:
            print(f"  OCR Space API Key: {api_key[:8]}...{api_key[-4:]} (length={len(api_key)})")
        else:
            print("  OCR Space API Key: MISSING!")
    except Exception as ex:
        print(f"  API Key check FAILED: {ex}")


def test_openai_service():
    print("\n=== Testing OpenAI Service (availability check) ===")
    try:
        from services.openai_service import openai_unavailable_message, configured_model
        unavailable = openai_unavailable_message()
        model = configured_model()
        if unavailable:
            print(f"  OpenAI UNAVAILABLE: {unavailable}")
        else:
            print(f"  OpenAI available, model={model}")
    except Exception as ex:
        print(f"  OpenAI Service FAILED: {ex}")


def test_nlp_service():
    print("\n=== Testing NLP Service (rule-based only) ===")
    try:
        from services.nlp_service import build_rule_based_summary
        summary = build_rule_based_summary(
            "Hemoglobin 10.2 g/dL. Glucose 250 mg/dL. Patient has diabetes.",
            "lab",
        )
        print(f"  NLP summary OK: {summary[:150]}")
    except Exception as ex:
        print(f"  NLP Service FAILED: {ex}")


async def test_full_pipeline():
    print("\n=== Testing Full AI Pipeline (end-to-end, no file upload) ===")
    try:
        from services.ocr_space_service import build_ocr_result
        from services.report_ai_pipeline import run_report_ai_pipeline

        sample_text = "Patient Name: Ahmed Khan\nAge: 55\nGender: Male\nHemoglobin: 9.8 g/dL\nGlucose: 310 mg/dL\nCreatinine: 2.5 mg/dL\nBlood Pressure: 160/95\nMedicine: Metformin 500mg, Aspirin 75mg"

        ocr_result = build_ocr_result(sample_text, "test_report.jpg")
        cleaned_text = ocr_result.get("cleaned_text", "")
        formatted_text = ocr_result.get("formatted_text", "")
        structured_payload = ocr_result.get("structured_data_json", {})
        department_name = ocr_result.get("department_name", "General")

        print(f"  OCR result: dept={department_name}, cleaned={len(cleaned_text)} chars")

        analysis = await run_report_ai_pipeline(
            cleaned_text=cleaned_text,
            formatted_text=formatted_text,
            structured_payload=structured_payload,
            department_name=department_name,
        )

        print(f"  Pipeline OK!")
        print(f"    Entities: {len(analysis.get('entities', []))}")
        print(f"    Validation status: {analysis.get('validation_status', 'UNKNOWN')}")
        print(f"    Summary source: {analysis.get('summary_source', 'UNKNOWN')}")
        print(f"    Confidence: {analysis.get('confidence_level', 'UNKNOWN')}")
        summary_text = analysis.get("summary_text", "")
        print(f"    Summary: {summary_text[:180]}")

        clinical = analysis.get("clinical_summary_json", {})
        print(f"    Clinical JSON keys: {list(clinical.keys())}")
        if clinical.get("key_findings"):
            print(f"    Key findings: {clinical['key_findings'][:3]}")
        if clinical.get("detected_diseases"):
            print(f"    Diseases: {clinical['detected_diseases'][:3]}")
        if clinical.get("medicines"):
            print(f"    Medicines: {clinical['medicines'][:3]}")

        self_check = analysis.get("llm_self_check", {})
        print(f"    Self-check: passed={self_check.get('passed')}, source={self_check.get('source')}")

    except Exception as ex:
        import traceback
        print(f"  Full pipeline FAILED: {ex}")
        traceback.print_exc()


def test_database():
    print("\n=== Testing Database Connection ===")
    try:
        from database import engine, Base
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"  Database connection OK: {result.fetchone()}")
    except Exception as ex:
        print(f"  Database FAILED: {ex}")


if __name__ == "__main__":
    print("=" * 60)
    print("NORA MEDLINK - COMPONENT TROUBLESHOOTING")
    print("=" * 60)

    test_ocr_space_api_key()
    test_openai_service()
    test_ocr_space_service()
    test_nlp_service()
    test_rule_validation()
    test_biobert_fallback()
    test_biobert()
    test_database()
    asyncio.run(test_full_pipeline())

    print("\n" + "=" * 60)
    print("TROUBLESHOOTING COMPLETE")
    print("=" * 60)
