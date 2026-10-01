"""Display saved evaluation results without running queries or models."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval/results/pilot-v1"
METHODS = {"local": "Local", "basic": "Basic", "global": "Global (tam rapor)", "drift": "DRIFT"}
CATEGORIES = {"concept": "Kavram", "connections": "Bağlantılar", "synthesis": "Genel açıklama", "unanswerable": "Cevaplanamaz"}


def load_eval_tables(method="Tümü"):
    try:
        rows = pd.read_csv(RESULTS / "results.csv")
        snapshot = json.loads((RESULTS / "questions.snapshot.json").read_text(encoding="utf-8"))
        manifest = json.loads((RESULTS / "manifest.json").read_text(encoding="utf-8"))
        required = {"case", "method", "category", "status", "seconds", "correctness_0_2",
                    "completeness_0_2", "source_support_0_2", "notes"}
        if not required.issubset(rows.columns):
            raise ValueError("Sonuç tablosunun sütunları eksik.")
        questions = {q["id"]: q["question"] for q in snapshot["questions"]}
        summary = []
        for key, label in METHODS.items():
            group = rows[rows["method"] == key]
            if group.empty:
                continue
            scored = group[group["correctness_0_2"].notna()]
            answerable = scored[scored["category"] != "unanswerable"]
            negative = scored[scored["category"] == "unanswerable"]
            complete = ((answerable["correctness_0_2"] == 2) & (answerable["completeness_0_2"] == 2)).sum()
            summary.append({"Yöntem": label,
                            "Doğruluk / 2": round(answerable["correctness_0_2"].mean(), 2),
                            "Tamlık / 2": round(answerable["completeness_0_2"].mean(), 2),
                            "Kaynak desteği / 2": round(answerable["source_support_0_2"].mean(), 2),
                            "Doğru ve tam": f"{complete}/{len(answerable)}",
                            "Uygun çekimserlik": f"{(negative['correctness_0_2'] == 2).sum()}/{len(negative)}",
                            "Ort. süre (sn)": round(group["seconds"].mean(), 1),
                            "Teknik başarı": f"{(group['status'] == 'ok').sum()}/{len(group)}"})
        visible = rows if method == "Tümü" else rows[rows["method"] == method]
        details = pd.DataFrame({
            "Soru no": visible["case"].str.split("-").str[0],
            "Soru": visible["case"].str.split("-").str[0].map(questions),
            "Tür": visible["category"].map(CATEGORIES),
            "Yöntem": visible["method"].map(METHODS),
            "Doğruluk / 2": visible["correctness_0_2"],
            "Tamlık / 2": visible["completeness_0_2"],
            "Kaynak / 2": visible["source_support_0_2"].fillna("Uygulanmaz"),
            "Süre (sn)": visible["seconds"].round(1),
            "Durum": visible["status"].map({"ok": "Tamamlandı", "error": "Hata", "timeout": "Süre aşımı"}),
            "Değerlendirme gerekçesi (İngilizce)": visible["notes"],
        })
        expected = len(questions) * len(METHODS)
        status = (f"**Kayıtlı deney: {manifest['started_utc'][:10]} · {len(questions)} soru · "
                  f"{len(rows)}/{expected} sorgu · {rows['correctness_0_2'].notna().sum()} puanlanmış cevap**\n\n"
                  "İngilizce pilot seti; Global tam rapor, topluluk düzeyi 0. Puanlar Codex'in kitap ve atıf metinleriyle "
                  "karşılaştırmasına dayanır; bağımsız uzman değerlendirmesi değildir. Bu ekran kayıtlı sonuçları gösterir.")
        return status, pd.DataFrame(summary), details.reset_index(drop=True)
    except (OSError, ValueError, KeyError) as exc:
        return f"Eval sonuçları okunamadı: {exc}", pd.DataFrame(), pd.DataFrame()
