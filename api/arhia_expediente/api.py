"""Capa API/UI de la plataforma (stdlib http.server) — entrada consumible del dictamen.

Endpoints:
- GET  /                -> dashboard HTML (formulario JSON + resultado)
- GET  /api/health      -> {"ok": true}
- POST /api/dictamen    -> recibe un payload JSON, ejecuta la plataforma y devuelve el
                           dictamen (JSON) + rutas de Markdown/HTML/PDF generados.

Sin dependencias externas. Ejecutar:  py -m arhia_expediente.api [--puerto 8080]
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from arhia_expediente.plataforma import dictamen_a_json, ejecutar_desde_json, generar_dictamen_markdown, generar_dictamen_html
from arhia_expediente.pdf_render import generar_dictamen_pdf

# Seguridad (P0-6): demo local. CORS solo localhost, cuerpo limitado, salida de servidor.
_MAX_BODY = 2 * 1024 * 1024
_SALIDA = os.path.join(os.path.dirname(__file__), "data", "api")
_LOCAL = ("127.0.0.1", "localhost")


def _cors(self):
    origin = self.headers.get("Origin", "")
    host = self.headers.get("Host", "").split(":")[0]
    if origin in ("http://" + host, "http://" + host + ":" + str(self.server.server_address[1])) or origin in ("null", "http://" + _LOCAL[0], "http://" + _LOCAL[1]):
        return origin
    return ""


def _sanitize_id(s):
    import re
    return re.sub(r"[^A-Za-z0-9_.-]", "_", (s or "caso"))[:60]

_DASHBOARD = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>ARHIAX — Dictamen</title>
<style>body{font-family:Arial;margin:24px auto;max-width:900px;padding:8px}h1{color:#10243f}
textarea{width:100%;height:220px;font-family:monospace;font-size:12px;padding:8px;box-sizing:border-box}
button{background:#10243f;color:#fff;border:0;padding:10px 18px;border-radius:6px;cursor:pointer}
.tag{display:inline-block;background:#10243f;color:#fff;padding:3px 10px;border-radius:12px;font-size:12px}
.exp{border:1px solid #ddd;border-left:4px solid #10243f;padding:8px 12px;margin:8px 0;border-radius:6px}
li{list-style:none}</style></head><body>
<h1>Plataforma ARHIAX — Dictamen Completo</h1>
<p>Pega el JSON de la operación (caso + contraparte + listas + señales) y ejecuta.</p>
<textarea id="inp" placeholder='{"caso":{"id":"DIC-1","tipo":"compraventa",...}}'></textarea><br><br>
<button onclick="run()">Ejecutar dictamen</button>
<b>Ejemplo</b> <button onclick="ejemplo()">Cargar ejemplo</button>
<div id="out"></div>
<script>
function ejemplo(){document.getElementById('inp').value=JSON.stringify(window.EJEMPLO,null,2);}
function run(){
  const body=JSON.parse(document.getElementById('inp').value);
  fetch('/api/dictamen',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(r=>r.json()).then(render).catch(e=>{document.getElementById('out').innerText='ERROR: '+e;});
}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function render(d){
  const ev=(d.eventos||[]).map(e=>'<li>['+esc(e.controlId)+'] '+esc(e.eventType)+' · hmac='+esc(e.hmacChain)+'</li>').join('');
  const hz=(d.hallazgos||[]).map(h=>'<div class="exp"><b>'+esc(h.id)+' · '+esc(h.titulo)+' ['+esc(h.estado)+']</b><div>'+esc(h.responsable)+'</div></div>').join('');
  document.getElementById('out').innerHTML=
    '<h2>'+esc(d.id)+' — <span class="tag">'+esc(d.veredicto)+'</span></h2>'
    +'<p>'+esc(d.fundamento)+'</p>'
    +'<p><b>Cumplimiento:</b> régimen '+esc(d.cumplimiento.regimen)+' · screening '+esc(d.cumplimiento.screening)
    +' · BF '+esc(d.cumplimiento.beneficiario_final)+' · perfil '+esc(d.cumplimiento.perfil)
    +' · inusual '+esc(d.cumplimiento.operacion_inusual)+'</p>'
    +'<ul>'+ev+'</ul><h3>Hallazgos</h3>'+hz
    +'<p style="color:#666;font-size:12px">Artefactos: '+esc((d.artefactos||[]).join(' · '))+'</p>';
}
window.EJEMPLO={"caso":{"id":"DIC-040-347004","tipo":"compraventa","predio":{"folio":"040-347004","catastro":"080010102000001710004000000000","direccion":"Barranquilla","areaRegistral":475,"areaCatastral":475},"partes":[{"rol":"vendedor","nombre":"PARQUE INDUSTRIAL CLAVERIA S.A.S","tipoDocumento":"nit","numeroDocumento":"900253457"},{"rol":"comprador","nombre":"INVERSIONES DEL CARIBE S.A.S","tipoDocumento":"nit","numeroDocumento":"901234567"}],"anotaciones":[{"numero":4,"tipo":"compraventa","fecha":"2014-11-05","titular":"PARQUE INDUSTRIAL CLAVERIA S.A.S"}],"avaluo":{"valor":1800000000},"precioPactado":1800000000,"pagos":[{"monto":1500000000,"medio":"transferencia","pagador":"MIGUEL ANTONIO VEGA","esTercero":true}]},"rolContraparte":"comprador","registroContraparte":{"nit":"901234567","razonSocial":"INVERSIONES DEL CARIBE S.A.S","ingresos":20000000000,"activos":25000000000,"sector":"inmobiliario","representanteLegal":"JOSE PEREZ","accionistas":[{"tipoDocumento":"cc","numeroDocumento":"1","nombre":"MIGUEL ANTONIO VEGA","participacion":0.6}]},"catalogoSenales":["pagoPorTercero","pagoFraccionado"],"patronNormal":500000000,"engine":"python"};
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        origin = _cors(self)
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        origin = _cors(self)
        self.send_response(204)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            return self._send(200, json.dumps({"ok": True}))
        return self._send(200, _DASHBOARD, "text/html")

    def do_POST(self):
        if self.path != "/api/dictamen":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > _MAX_BODY:
                return self._send(413, json.dumps({"error": "cuerpo demasiado grande"}))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            return self._send(400, json.dumps({"error": "bad json: " + str(e)}))
        try:
            if payload.get("listasVivas"):
                from arhia_sag_screen.ingest.listas import preparar_screening
                regs, lista = preparar_screening(payload.get("listasFuente", "onu"))
                payload["registrosLista"] = [
                    {"id": r.id, "nombre": r.nombre, "alias": list(r.alias),
                     "tipoDocumento": r.tipo_documento, "numeroDocumento": r.numero_documento,
                     "fuente": r.fuente, "listaVersion": r.listaVersion} for r in regs]
                payload["screening"] = {"fuente": lista.fuente, "version": lista.version, "hash": lista.hash}
            d = ejecutar_desde_json(payload)
            out = dictamen_a_json(d)
            artefactos = []
            # Salida controlada por el servidor (no por el cliente) + id saneado (P0-6).
            os.makedirs(_SALIDA, exist_ok=True)
            base = os.path.join(_SALIDA, "dictamen_" + _sanitize_id(d.caso.id))
            md_path = base + ".md"
            html_path = base + ".html"
            pdf_path = base + ".pdf"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(generar_dictamen_markdown(d))
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(generar_dictamen_html(d))
            generar_dictamen_pdf(d, pdf_path)
            artefactos = [os.path.abspath(md_path), os.path.abspath(html_path), os.path.abspath(pdf_path)]
            out["artefactos"] = artefactos
            return self._send(200, json.dumps(out, ensure_ascii=False))
        except Exception as e:
            return self._send(500, json.dumps({"error": str(e)}))

    def log_message(self, fmt, *args):
        os.environ.get("ARHIAX_SILENCIO") or print("[api] " + (fmt % args))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    srv = ThreadingHTTPServer((args.host, args.puerto), Handler)
    print("Plataforma ARHIAX activa en http://%s:%d/  (POST /api/dictamen)" % (args.host, args.puerto))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
