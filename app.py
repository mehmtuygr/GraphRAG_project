from __future__ import annotations
import os
import subprocess
import sys
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
import gradio as gr
from scripts.query_process import run_query_process
from scripts.eval_view import load_eval_tables
from scripts.graph_view import find_entities, render_graph

ROOT = Path(__file__).resolve().parent



def graphrag_ask(question: str, method: str, response_type: str, community_level=0, full_reports=False):
    question = (question or "").strip()
    if not question:
        yield "Lütfen bir soru yaz."
        return
    method = (method or "local").lower()
    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_local.py"), "query", question,
        "--method", method,
        "--response-type", response_type or "Multiple Paragraphs",
    ]
    if method in {"global", "drift"}:
        cmd += ["--community-level", str(int(community_level))]
    if method == "global" and full_reports:
        cmd += ["--full-reports"]
    yield "Soru alındı. Kitapta ilgili bilgiler aranıyor ve yerel model hazırlanıyor…"
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    with tempfile.NamedTemporaryFile(prefix="udl-progress-", suffix=".txt", delete=False) as progress_file:
        progress_path = Path(progress_file.name)
    env["UDL_QUERY_PROGRESS_FILE"] = str(progress_path)
    started = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                run_query_process, cmd, timeout=900, cwd=ROOT, env=env,
            )
            while True:
                try:
                    p = future.result(timeout=2)
                    break
                except FutureTimeout:
                    elapsed = int(time.monotonic() - started)
                    try:
                        stage = progress_path.read_text(encoding="utf-8", errors="replace").strip()
                    except OSError:
                        stage = ""
                    yield f"{stage or 'Yanıt hazırlanıyor…'} **{elapsed} saniye** geçti."
    except FileNotFoundError:
        yield "GraphRAG bulunamadı. Önce: pip install -r requirements.txt"
        return
    except subprocess.TimeoutExpired:
        yield "Sorgu 15 dakikayı aştı. Ollama'nın açık olduğunu kontrol et."
        return
    except Exception as e:
        yield f"Sorgu çalıştırılamadı: {type(e).__name__}: {e}"
        return
    finally:
        progress_path.unlink(missing_ok=True)
    if p.returncode != 0:
        yield f"GraphRAG hatası:\n\n```text\n{(p.stderr or p.stdout)[-4000:]}\n```"
        return
    yield p.stdout.strip() or "Model boş yanıt döndürdü. Ollama'yı kontrol edip daha kısa bir soruyla tekrar dene."


with gr.Blocks(title="Understanding Deep Learning - GraphRAG") as demo:
    gr.Markdown("# Understanding Deep Learning - GraphRAG\nMicrosoft GraphRAG + Yerel Ollama (Qwen / EmbeddingGemma)")
    with gr.Tab("Kitaba Sor"):
        with gr.Row():
            method = gr.Dropdown(["local", "global", "drift", "basic"], value="local", label="Arama yöntemi")
            response_type = gr.Dropdown(["Single Sentence", "List of 3-7 Points", "Multiple Paragraphs"], value="Multiple Paragraphs", label="Yanıt biçimi")
        community_level = gr.Dropdown(
            [("0 — Genel temalar (daha hızlı)", 0),
             ("1 — Daha ayrıntılı (daha yavaş)", 1),
             ("2 — İnce ayrıntılar (çok daha yavaş)", 2)],
            value=0, label="Global / DRIFT topluluk düzeyi",
        )
        full_reports = gr.Checkbox(value=False, label="Global: özetler yerine tam raporları tara (daha ayrıntılı, daha yavaş)")
        gr.Markdown("**Global:** seçilen düzeydeki topluluk raporlarını tarar. **DRIFT:** ilgili topluluklardan başlayıp iki turda, tur başına en fazla iki takip sorusuyla grafiği araştırır. 0. düzey daha hızlıdır; ince ayrıntılar özetlerde kaybolabilir.")
        q = gr.Textbox(lines=3, label="Soru", placeholder="Örn: Transformers ile graph neural networks arasındaki temel farklar nelerdir?")
        ask = gr.Button("Sor", variant="primary")
        ans = gr.Markdown()
        ask.click(graphrag_ask, [q, method, response_type, community_level, full_reports], ans, concurrency_limit=1, concurrency_id="local_query")
        q.submit(graphrag_ask, [q, method, response_type, community_level, full_reports], ans, concurrency_limit=1, concurrency_id="local_query")
        gr.Markdown("**İpucu:** belirli kavram/algoritma için `local`; kitabın genel temaları için `global`; çok adımlı bağlantılar için `drift`; klasik semantik RAG için `basic`.")

    with gr.Tab("Graf Keşfi"):
        gr.Markdown("## Kitaptaki kavramlar nasıl bağlantılı?\nBir kavram ara, listeden seç ve grafiği aç. Görünüm kayıtlı indeksten oluşturulur; model çağrısı yapmaz.")
        with gr.Row():
            graph_term = gr.Textbox(label="Kavram ara", value="backpropagation")
            graph_search = gr.Button("Kavramları bul")
        graph_entity = gr.Dropdown(choices=[], label="Eşleşen kavramlar (en fazla 60)")
        with gr.Row():
            graph_hops = gr.Radio([1, 2], value=1, label="Bağlantı uzaklığı")
            graph_limit = gr.Slider(5, 80, value=30, step=5, label="En fazla kavram")
        graph_show = gr.Button("Grafiği göster", variant="primary")
        gr.Markdown("Kalabalığı azaltmak için yüksek ağırlıklı bağlantılara öncelik verilir. Bu grafik belirli bir cevabın izlediği yolu değil, kayıtlı kavram ilişkilerini gösterir.")
        graph_html = gr.HTML()

        def search_graph(term):
            try:
                choices = find_entities(term)
            except (OSError, ValueError, KeyError) as exc:
                raise gr.Error(f"Grafik okunamadı: {exc}") from exc
            if not choices:
                gr.Info("Eşleşme bulunamadı. İngilizce bir kavram adı dene.")
            return gr.Dropdown(choices=choices, value=choices[0] if choices else None)

        graph_search.click(search_graph, graph_term, graph_entity)
        graph_term.submit(search_graph, graph_term, graph_entity)
        graph_show.click(render_graph, [graph_entity, graph_hops, graph_limit], graph_html)

    with gr.Tab("Eval Sonuçları") as eval_tab:
        gr.Markdown("## Cevap kalitesi değerlendirmesi")
        eval_status = gr.Markdown("Sekme açıldığında kayıtlı değerlendirme yüklenir.")
        eval_summary = gr.Dataframe(interactive=False, label="Yöntem karşılaştırması", wrap=True)
        gr.Markdown("**Puanlar:** 0 = başarısız, 1 = kısmi, 2 = iyi. Doğruluk, tamlık ve kaynak ortalamaları kitapta cevaplanabilen 10 soruya aittir. **Doğru ve tam**, hem doğruluk hem tamlık puanı 2 olan cevapları sayar; diğer cevapların hepsi yanlış değildir. **Uygun çekimserlik**, cevaplanamayan iki soruda uydurmadan ve yanlış ek iddialar katmadan yanıt vermeyi ölçer. Süreler tüm 12 sorunun ortalamasıdır; sonraki sorguların süresini garanti etmez.")
        with gr.Row():
            eval_method = gr.Dropdown(choices=[("Tüm yöntemler", "Tümü"), ("Local", "local"), ("Basic", "basic"), ("Global", "global"), ("DRIFT", "drift")], value="Tümü", label="Soru tablosunu filtrele")
            eval_refresh = gr.Button("Kayıtlı sonuçları yenile")
        eval_details = gr.Dataframe(interactive=False, label="Soru bazında puanlar ve gerekçeler", wrap=True)
        gr.Markdown("**Nasıl yorumlamalı?** Teknik başarı, sorgunun hatasız tamamlanmasıdır; doğru cevap garantisi değildir. Kaynak numarasının mevcut olması da iddiayı desteklediğini kanıtlamaz. Cevaplanamaz sorularda kaynak puanı uygulanmayabilir. Yenile düğmesi yalnızca sonuç dosyalarını okur; eval testini veya modeli çalıştırmaz.")
        eval_outputs = [eval_status, eval_summary, eval_details]
        eval_tab.select(load_eval_tables, eval_method, eval_outputs)
        eval_refresh.click(load_eval_tables, eval_method, eval_outputs)
        eval_method.change(load_eval_tables, eval_method, eval_outputs)

    with gr.Tab("Durum"):
        gr.Markdown("""
- `input/`: PDF'den çıkarılmış sayfa-izli metinler
- `output/`: Microsoft GraphRAG parquet + LanceDB çıktıları
- Gradio: Local / Global / DRIFT / Basic GraphRAG sorguları
        """)

if __name__ == "__main__":
    demo.queue().launch(inbrowser=True, show_error=True)
