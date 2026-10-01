"""Audit reference IDs and export evaluation results; semantic scores need review."""
import argparse
import csv
import json
from pathlib import Path
import re
import statistics

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r'\b(Reports|Sources|Entities|Relationships)\s*((?:\([^)]*\)\s*,?\s*)+)', re.I)


def reference_tables():
    specs = {'sources':('text_units','human_readable_id','text'),
             'entities':('entities','human_readable_id','description'),
             'relationships':('relationships','human_readable_id','description'),
             'reports':('community_reports','community','full_content')}
    tables = {}
    for kind,(name,key,content) in specs.items():
        frame = pd.read_parquet(ROOT/'output/local'/f'{name}.parquet')
        tables[kind] = {str(row[key]):row for row in frame.to_dict('records')}
    return tables, specs


def citations(answer, tables):
    found = []
    groups = [(m.group(1), ','.join(re.findall(r'\(([^)]*)\)',m.group(2)))) for m in PATTERN.finditer(answer)]
    groups += re.findall(r'\[(Reports|Sources|Entities|Relationships):\s*([\d.,\s]+)\]',answer,re.I)
    for kind, ids in groups:
        for value in ids.split(','):
            value = value.strip()
            if value.lower() in {'+more','more','...'}:
                continue
            found.append({'kind':kind.lower(),'id':value,'exists':value in tables[kind.lower()]})
    return list({(x['kind'],x['id']):x for x in found}.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',default='eval/results/pilot-v1')
    args = parser.parse_args()
    out = ROOT/args.out
    tables,specs = reference_tables()
    review_path = out/'review.json'
    reviews = json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    dataset = json.loads((out/'questions.snapshot.json').read_text(encoding='utf-8'))
    questions = {q['id']:q for q in dataset['questions']}
    rows, evidence = [], []
    evidence_dir = out/'evidence'
    evidence_dir.mkdir(exist_ok=True)
    for path in sorted(out.glob('q??-*.json')):
        case_start = len(evidence)
        result = json.loads(path.read_text(encoding='utf-8'))
        refs = citations(result['answer'],tables)
        review = reviews.get(path.stem,{})
        rows.append({'case':path.stem,'category':questions[result['question_id']]['category'],
                     'method':result['method'],'status':result['status'],'seconds':result['seconds'],
                     'reference_ids':len(refs),'existing_reference_ids':sum(r['exists'] for r in refs),
                     'correctness_0_2':review.get('correctness',''),
                     'completeness_0_2':review.get('completeness',''),
                     'source_support_0_2':review.get('source_support',''),
                     'notes':review.get('notes','Not yet reviewed')})
        evidence.append(f"# {path.stem}\n\nQuestion: {questions[result['question_id']]['question']}\n\n## Answer\n\n{result['answer']}\n\n## Expected points\n\n"+'\n'.join('- '+p for p in questions[result['question_id']]['expected']))
        for ref in refs:
            row = tables[ref['kind']].get(ref['id'])
            content = str(row.get(specs[ref['kind']][2],'')) if row is not None else 'REFERENCE ID NOT FOUND'
            evidence.append(f"\n### {ref['kind']} ({ref['id']})\n\n{content}")
        (evidence_dir/f'{path.stem}.md').write_text('\n\n'.join(evidence[case_start:]),encoding='utf-8')
    if rows:
        with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    (out/'evidence.md').write_text('\n\n'.join(evidence),encoding='utf-8')
    (out/'citation_audit.json').write_text(json.dumps({p.stem:citations(json.loads(p.read_text(encoding='utf-8'))['answer'],tables) for p in sorted(out.glob('q??-*.json'))},ensure_ascii=False,indent=2),encoding='utf-8')
    for method in ('basic','local','global','drift'):
        subset = [r for r in rows if r['method']==method]
        if subset:
            print(method,len(subset),'completed;',round(statistics.mean(r['seconds'] for r in subset),1),'mean seconds;',sum(r['status']=='ok' for r in subset),'successful processes')
    report = ['# GraphRAG eval sonuçları', '', '[Bulgular ve yorumlar](FINDINGS.md)', '',
              f'Tamamlanan sorgu: **{len(rows)}/48**. İncelenen cevap: **{sum(r["correctness_0_2"] != "" for r in rows)}/{len(rows)}**.', '',
              '12 İngilizce soru × 4 yöntem. 10 soru kitapta cevaplanabilir; 2 soru cevaplanamaz negatif kontroldür. Global tam rapor modunda ve topluluk düzeyi 0 ile çalıştırıldı. Ayarlar deney sırasında değiştirilmedi.', '',
              'Puanlar 0–2 ölçeğinde Codex tarafından kaynak metin ve atıflarla karşılaştırılarak verilmiştir; bağımsız uzman veya kör değerlendirme değildir. Bu küçük pilot genel bir doğruluk yüzdesi değildir.', '',
              '## Yöntem karşılaştırması', '',
              '| Yöntem | Süre ort. (sn) | Süre medyanı (sn) | Doğru ve tam / cevaplanabilir | Doğruluk ort. (0–2) | Kaynak desteği ort. (0–2) | Uygun çekimserlik / negatif |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for method in ('basic','local','global','drift'):
        subset = [r for r in rows if r['method']==method]
        if not subset:
            continue
        answerable = [r for r in subset if r['category']!='unanswerable' and r['correctness_0_2']!='']
        negative = [r for r in subset if r['category']=='unanswerable' and r['correctness_0_2']!='']
        good = sum(r['correctness_0_2']==2 and r['completeness_0_2']==2 for r in answerable)
        abstain = sum(r['correctness_0_2']==2 for r in negative)
        correctness = f"{statistics.mean(r['correctness_0_2'] for r in answerable):.2f}" if answerable else '—'
        support = f"{statistics.mean(r['source_support_0_2'] for r in answerable):.2f}" if answerable else '—'
        report.append(f"| {method} | {statistics.mean(r['seconds'] for r in subset):.1f} | {statistics.median(r['seconds'] for r in subset):.1f} | {good}/{len(answerable)} | {correctness} | {support} | {abstain}/{len(negative)} |")
    report += ['', 'Doğru ve tam sayısı, doğruluk=2 ve tamlık=2 şartını birlikte arar; kaynak doğruluğunu ayrıca garanti etmez. Doğruluk ve kaynak ortalamaları yalnızca cevaplanabilir sorular içindir. Cevaplanabilir soruda yanıtsız kalma 0 puan alır. Süreler birer çalıştırmanın gözlemidir.', '',
               '## Soru türüne göre doğru ve tam cevaplar', '',
               '| Tür | Basic | Local | Global | DRIFT |','|---|---:|---:|---:|---:|']
    for category in ('concept','connections','synthesis'):
        values=[]
        for method in ('basic','local','global','drift'):
            subset=[r for r in rows if r['category']==category and r['method']==method and r['correctness_0_2']!='']
            values.append(f"{sum(r['correctness_0_2']==2 and r['completeness_0_2']==2 for r in subset)}/{len(subset)}")
        report.append('| '+category+' | '+' | '.join(values)+' |')
    report += ['', '## Atıf kimlik kontrolü', '', '| Yöntem | İndekste bulunan / ayrıştırılan ID |', '|---|---:|']
    for method in ('basic','local','global','drift'):
        subset=[r for r in rows if r['method']==method]
        report.append(f"| {method} | {sum(r['existing_reference_ids'] for r in subset)}/{sum(r['reference_ids'] for r in subset)} |")
    report += ['', 'Bu kontrol Sources/Entities/Relationships/Reports (ID) biçimini ayrıştırır; serbest metin ve bozuk atıfların tamamını kapsamaz. Her cevap içindeki tekrarlar tekilleştirilir. Bir ID’nin bulunması, kaynağın iddiayı desteklediğini veya sorguya getirildiğini kanıtlamaz.', '',
               '## Tek tek değerlendirmeler', '', '| Soru / yöntem | Doğruluk | Tamlık | Kaynak | Gerekçe |', '|---|---:|---:|---:|---|']
    for row in rows:
        note = row['notes'].replace('|','/').replace('\n',' ').replace('<','&lt;').replace('>','&gt;')
        report.append(f"| [{row['case']}](evidence/{row['case']}.md) | {row['correctness_0_2']} | {row['completeness_0_2']} | {row['source_support_0_2'] if row['source_support_0_2'] is not None else 'Uygulanmaz'} | {note} |")
    report += ['', '## Dosyalar ve sınırlar', '',
               '- `results.csv`: puanlar, süreler ve işlem durumları.',
               '- `qXX-yöntem.json`: değişmeden saklanan cevap ve hata çıktısı.',
               '- `evidence/`: her cevabın atıflarının indeksteki metinleri. Bunlar getirilen bağlamın tam kaydı değil, sonradan yapılan atıf çözümlemesidir.',
               '- `review.json`: gerekçeli değerlendirme puanları.',
               '- `manifest.json`, `settings.snapshot.yaml`, `questions.snapshot.json`: deney koşulları.',
               '- Önceki önbellek, model yükleme süresi ve arka plan yükü kontrol edilmedi. DRIFT ve üretim sonuçları tekrar çalıştırmada değişebilir.',
               '- Referans raporları da model üretimidir; rapora sadık bir cevap kitap açısından yine hatalı olabilir.',
               '- Türkçe soru kalitesi ve kapsamlı retrieval precision/recall bu deneyde ölçülmedi.']
    (out/'REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print('Reference existence is NOT proof of supporting evidence. Semantic scores are reviewed separately.')


if __name__ == '__main__':
    main()
