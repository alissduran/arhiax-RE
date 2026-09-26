# HOTFIX 2.0B-R1.1 — MIGRACIÓN 003 / CREACIÓN DE CASO EN PRODUCCIÓN

**Veredicto:** `DICTUS 2.0B-R1.1 — PROD CASE CREATION RESTORED`
(fix desplegado, smoke real en `arhiax-re.vercel.app` verde, base dejada como estaba).

---

## 1 · Causa raíz exacta

`api/migrations.py::_apply_documento_principal` declaraba el tipo de la columna binaria
**literal**, con el nombre de SQLite, para **todos** los dialectos:

```sql
ALTER TABLE trabajos_pdf ADD COLUMN IF NOT EXISTS pdf_tecnico BLOB
```

Ese DDL se ejecuta contra **PostgreSQL/Neon**, donde `BLOB` no es un tipo válido
(`type "blob" does not exist`, `UndefinedObject`) — el tipo binario de Postgres es
`BYTEA`.

Cadena del fallo (confirmada sobre el código desplegado en `ffa548d`):

```
POST /api/dictamenes
  └─ case_service.create_case()
       └─ CaseRepository.insert()
            └─ database.get_db_connection()
                 └─ migrations.ensure_migrated(conn)
                      └─ migrations.run_migrations(conn)
                           └─ 003_documento_principal → ALTER ... BLOB   ← ERROR DDL
```

Es decir: el fallo ocurría **antes** de escribir el caso, en la apertura de la conexión
— por eso `POST /api/dictamenes` devolvía 500 («No se pudo crear el caso en el
servidor») y **toda** consulta a la base quedaba inservible: la migración nunca se
registraba y se reintentaba en cada petición. En Postgres el error DDL además dejaba la
transacción abortada.

**Por qué no lo detectó la suite:** SQLite acepta `BLOB`, y el camino Postgres solo
estaba cubierto por la migración `001` (`postgres_adapter.init_postgres`, que sí usaba
`BYTEA`); la migración `003` no tenía prueba de dialecto.

### Evidencia (SQL emitido, por dialecto)

```
DIALECTO POSTGRES/NEON · aplicadas: ['003_documento_principal']
    ALTER TABLE trabajos_pdf ADD COLUMN IF NOT EXISTS pdf_tecnico BYTEA      ← corregido
    ALTER TABLE trabajos_pdf ADD COLUMN IF NOT EXISTS manifest_json TEXT
    ALTER TABLE trabajos_pdf ADD COLUMN IF NOT EXISTS folio TEXT

DIALECTO SQLITE · aplicadas: ['003_documento_principal']
    ALTER TABLE trabajos_pdf ADD COLUMN pdf_tecnico BLOB                     ← local, correcto
    ...
```

Se reproduce con `python scripts/diagnostico_migracion_dialecto.py`.

> Nota de honestidad: **no se pudo leer el log de Vercel** desde este entorno (sin CLI
> de Vercel ni token de la cuenta; la red solo alcanza la API pública). La causa raíz
> no es una hipótesis: el SQL que la migración emitía para Postgres es reproducible y
> `BLOB` es inválido en Postgres, y esa rama se ejecuta antes de cualquier escritura.
> El reemplazo del log es la verificación en producción de la sección 5.

## 2 · Cambio realizado

| Archivo | Cambio |
|---|---|
| `api/migrations.py` | `_tipo_binario()`: tipo binario POR DIALECTO (`BYTEA` en Postgres, `BLOB` en SQLite); `003` lo usa. `_normalizar_tipo()`: red de seguridad del runner con **una sola regla** idempotente (`BLOB`/`BYTEA` → tipo del dialecto; `AUTOINCREMENT`/`DATETIME` → `SERIAL`/`TIMESTAMP`). |
| `api/migrations.py` | `run_migrations()`: la migración se registra en `schema_migrations` **solo** si todos sus pasos terminaron; ante un fallo hace **rollback** (deja la conexión utilizable), la migración queda **pendiente** y la excepción se propaga. |
| `api/index.py` | `create_dictamen()`: registro **server-side** con traza (`log.exception`) para fallos de persistencia y respuesta genérica («No fue posible crear el caso.»). Sin DSN, sin SQL con credenciales, sin stack trace en la respuesta. |
| `tests/test_hotfix_migraciones_postgres.py` | 14 pruebas nuevas (dialecto, registro, rollback, idempotencia, estado parcial, flujo de caso). |
| `scripts/diagnostico_migracion_dialecto.py`, `scripts/smoke_prod_case_creation.py`, `scripts/smoke_prod_dictus_run.py` | Evidencia y verificación repetible (las contraseñas llegan por entorno/archivo, nunca por argumento ni salida). |

**No se tocó** nada más: ni renderer ejecutivo, ni `DictusRunState`, ni hash maestro,
ni POT, ni screening, ni SAGRILAFT, ni valoración, ni identidad, ni POI, ni retículas.

## 3 · Estado de la migración 003

* El SQL corregido se aplica en Neon: las consultas que **leen** las columnas nuevas
  (`folio`, `pdf_tecnico`, `manifest_json`) responden `404 Trabajo no encontrado` en
  lugar de `500 column does not exist`.
* El registro en `schema_migrations` ocurre en la misma transacción que el DDL exitoso;
  un fallo no registra la migración (probado).
* La migración es idempotente y funciona con estado parcial (una columna ya existente).

## 4 · Smoke real en producción (§9 y §10)

Contra `https://arhiax-re.vercel.app` (login real, usuario `admin`):

| Paso | Resultado |
|---|---|
| `POST /api/login` | **200** |
| `POST /api/dictamenes` (el endpoint del incidente) | **200** · `{"id": 12, "folio_matricula": "000-000999", "direccion": "SMOKE 2.0B-R1.1 PRUEBA DE CREACION DE CASO", "ciudad": "barranquilla", "estado": "PENDIENTE_IMAGENES", "created_by": "admin"}` |
| `GET /api/dictamenes` | **200** · el caso creado aparece en el listado |
| `GET /api/v1/pdf/trabajos/{job}` · `/anexo-tecnico` · `/manifest` | **404** (columnas de la entrega presentes en Neon; sin escritura) |
| `DELETE /api/dictamenes/{id}` | **200** · ningún caso de prueba queda en la base |

Segunda corrida (generación completa, §10) — `POST /api/dictamenes/generar` con el CTL
del caso 040-646406:

| Evidencia | Valor |
|---|---|
| HTTP | **200** |
| `X-Arhiax-Documento` | **DICTUS_EJECUTIVO** |
| `Content-Disposition` | `attachment; filename="DICTUS_EJECUTIVO_040-646406.pdf"` |
| `X-Arhiax-Paginas-Ejecutivo` | **6** |
| `X-Arhiax-Anexo-Tecnico` | `DICTUS_TECNICO_040-646406.pdf` · sha256 `7862e4362c498b422f50470756bb737f8ec5a44397f096b8067cd8275aa4681f` |
| `X-Arhiax-Master-Hash` | `dea0743c81004f8f83060e4e08bc29aa72808905ee021b09e7eca892e4e7aca7` (impreso en el documento) |
| `X-Arhiax-Dictus-Id` | `DX-040-646406-20260926` |
| sha256 del PDF recibido | `7e3577c26a7855c2808aa4159faa42df770e52dcfe6090db680bb48e7a7ffa2a` |
| Contrato del PDF | 6 páginas · página 1 = «RESUMEN DE DECISIÓN» · sin capítulos legacy · sin fugas técnicas |

PDF de la verificación: `tmp_smoke_prod/DICTUS_EJECUTIVO_040-646406_PROD.pdf`
(no versionado: `*.pdf` está ignorado). El cambio de migración **no afecta** al
Ejecutivo, al Técnico, al manifest, al hash maestro, a los jobs ni al worker: la corrida
real los produjo con normalidad.

## 5 · Pruebas y despliegue

* `tests/test_hotfix_migraciones_postgres.py`: **14 passed**.
* Suite offline completa: **836 passed, 0 failed, 2 skipped, 11 deselected**.
* Commit del hotfix: `cc12a2d` (`ffa548d..cc12a2d` en `main`), desplegado y verificado
  por los smokes de las secciones 4.

## 6 · Lo que NO se pudo hacer desde este entorno

* **Log de Vercel**: sin CLI ni token de la cuenta no fue posible consultarlo; se
  sustituyó por la reproducción del SQL emitido y por el smoke en producción (la
  hipótesis queda confirmada por el comportamiento observable, no por el log).
* **Acceso directo a Neon**: no hay DSN local; la comprobación de esquema se hizo por
  API (lectura, sin escritura).
