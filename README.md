# Mandarim Tech AI — Backend (v0.3: HSK 3.0 + SRS + TTS)

API em **FastAPI** para aprender mandarim (preparatório do **Novo HSK 3.0**) com foco em vocabulário
técnico de TI, ERP e Negócios — inclusive para quem nunca viu Hanzi. O **Pinyin é cidadão de primeira
classe**: toda resposta traz tons numéricos e guia fonético em português.

## Instalação e execução

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload      # Swagger: http://127.0.0.1:8000/docs
pip install -r requirements-dev.txt && pytest -q   # 164 testes (+1 opcional com internet)
```

> **Atualizando da v0.2?** Nada a apagar: a tabela de revisões (`user_card_reviews`) é criada
> sozinha e o seeder gera um cartão para cada termo existente. Rode `pip install -r requirements.txt`
> (nova dependência: `edge-tts`).
>
> **Atualizando da v0.1?** O schema mudou (novas colunas). Apague o `mandarim_tech.db` antigo e
> reinicie; o app avisa com uma mensagem clara se detectar um banco desatualizado.

## Guia rápido no Swagger (`/docs`)

1. **`GET /api/vocabulary`** → *Try it out*. Experimente:
   `search=shuju` (Pinyin sem tom), `search=shu4ju4ku4`, `hsk_level=HSK1_3.0`,
   `category=ERP`, `is_handwriting_required=true`. Cada termo traz `pinyin_numeric`,
   `pinyin_guide` e `radical_breakdown`.
2. **`GET /api/vocabulary/hsk-levels`** → metas acumuladas (300/500/1.000/2.000) e quantos termos
   estão cadastrados por nível.
3. **`POST /api/grammar/compile`** → cole o exemplo (o botão *Example* já vem preenchido):
   ```json
   {"subject": "wo", "time": "zuotian", "verb": "xiufu", "object": "bug", "completed": true}
   ```
   Resultado: `我昨天修复bug了。` · `Wo3 zuo2tian1 xiu1fu4 bug le0`. Use `place: "gongsi"` para ver o 在
   inserido automaticamente, `le_position: "after_verb"` e `target_level` para a checagem de nível.
4. **`POST /api/ai/coach`** → aceita Hanzi ou Pinyin bruto:
   `{"sentence": "我是很忙。"}` ou `{"sentence": "wo shi hen mang"}`.

5. **`GET /api/srs/due`** → cartões devidos (`total_due` + `items`, mais antigos primeiro; `limit` 1-100).
   Em seguida **`POST /api/srs/review`** com `{"term_id": 1, "grade": 4}`: veja `interval`,
   `repetition`, `ease_factor` e `next_review_date` mudarem. Notas: 0-2 errou, 3 difícil, 4 bom, 5 perfeito.
6. **`GET /api/tts/generate`** → `text=你好，我是程序员。`, `voice=female|male`, `rate=-10%`. O Swagger
   toca o MP3 direto no navegador. Via `curl`, o `+` precisa ser codificado:
   `curl -G .../api/tts/generate --data-urlencode "text=你好" --data-urlencode "rate=+0%" -o oi.mp3`.

## Estrutura

```
app/
├── main.py  config.py  database.py   # app, settings, engine + guarda de schema
├── models.py                          # VocabularyTerm, TermCategory, HSKLevel
├── schemas.py  exceptions.py  hsk.py  # contratos, erros de domínio, metas por nível
├── text_utils.py                      # Hanzi/Pinyin: normalização, sílabas, tons numéricos
├── pinyin_guide.py                    # guia fonético PT-BR (gerado por regras)
├── seed_data.py  seeder.py            # 68 termos, glossário de caracteres, seeder idempotente
├── data/handwriting_characters.txt    # lista de caligrafia (书写字) — preencha (veja abaixo)
├── timeutils.py                       # relógio UTC + coluna DateTime sempre com fuso
├── routers/   vocabulary.py  grammar.py  ai_coach.py  srs.py  tts.py
└── services/  lexicon.py  vocabulary_service.py  grammar_service.py
               ai_coach_service.py  llm_client.py  srs_service.py  tts_service.py
tests/  conftest.py test_api.py test_hsk_vocabulary.py test_grammar.py
        test_coach_pinyin.py test_text_utils.py test_schema_guard.py
        test_srs.py test_tts.py
```

## Decisões e limitações importantes

**Metas do HSK 3.0.** Usamos as metas acumuladas da revisão em vigor desde julho de 2026:
HSK 1 = 300, HSK 2 = 500, HSK 3 = 1.000, HSK 4 = 2.000. Listas anteriores (rascunho de 2021)
usam 500 / 1.272 / 2.245 / 3.245 — é o caso do PDF "NEW(3.0) HSK1 500 words". Ajuste em `app/hsk.py`.

**Níveis dos termos.** `HSK1_3.0`: as 43 palavras conferem com a lista de 500 palavras de HSK 1
(2021); a revisão de 2026 pode ter movido algumas para o nível 2. `HSK2_3.0`: 公司 (lista HSK 2.0 de
nível 2) e 程序/网络 (classificação definida pelo projeto; **não verificada** na lista de 2026 —
网络 é HSK 6 no HSK 2.0). `HSK_TECH`: vocabulário técnico fora das listas oficiais. O vocabulário
cadastrado é um conjunto curado, **não** as listas completas.

**Caligrafia (书写字).** Os mecanismos existem (coluna, filtro, sincronização a cada start), mas
a lista **não é fornecida**: as fontes consultadas divergem sobre quais caracteres são exigidos e
em que nível. Copie a lista oficial para `app/data/handwriting_characters.txt`; um termo é marcado
quando **todos** os seus caracteres estão na lista.

**Radicais.** `radical_breakdown` traz um bloco por caractere (significado e, quando certo, o
radical semântico). A decomposição completa em componentes não foi feita.

**Guia fonético.** Aproximação por regras (zh = "dj", q = "tch", x = "ch" suave...), pensada para
iniciantes; não substitui áudio.

**AI Coach.** `MockLLMClient` continua sendo uma simulação por regras (5 erros típicos), agora com
metáforas computacionais e nível HSK estimado (heurístico). Pinyin bruto é convertido para Hanzi
usando **apenas o vocabulário cadastrado**; palavras desconhecidas retornam 422 listando-as. Tons
digitados são ignorados na conversão. Para um LLM real, implemente `LLMClient`.

**Compilador de frases.** A checagem é um checklist didático inspirado nas tarefas de montagem de
frases do HSK 3.0, não uma correção oficial. Termos não chineses (ex.: `bug`) passam intactos.

## v0.3 — Repetição espaçada (SRS) e áudio (TTS)

**SM-2.** Implementação fiel ao algoritmo original (`app/services/srs_service.py`): nota ≥ 3 →
intervalos 1 dia, 6 dias e depois `round(intervalo × EF)` (.5 arredonda para cima);
`EF' = EF + (0,1 − (5−q)·(0,08 + (5−q)·0,02))`, mínimo 1,3. Nota 0-2 reinicia as repetições
(`repetition = 0`, `interval = 1`) **sem alterar o EF**, como no texto original — várias
implementações populares alteram o EF também no erro, então os intervalos podem diferir delas.
Datas são sempre UTC com fuso (`...Z`).

**Cartões.** O seeder cria um cartão por termo, já devido (`interval = 0`); termos novos ganham
cartão automaticamente no próximo start, e `POST /review` cria o cartão se ele não existir. Não há
contas de usuário: existe **um** cartão por termo (para vários alunos, adicione `user_id`).
`POST /review` recebe `term_id` **e** `grade` (o `term_id` é necessário para saber qual cartão avaliar).

**TTS.** `edge-tts` com as vozes `zh-CN-XiaoxiaoNeural` (female) e `zh-CN-YunxiNeural` (male). O
texto precisa ter Hanzi (até 300 caracteres) e a velocidade fica entre −50% e +100% (limite
desta API). Os MP3 ficam em cache em disco (`TTS_CACHE_DIR`, padrão: pasta temporária do sistema),
indexados por hash de voz+velocidade+texto; não há limpeza automática — pode apagar a pasta quando
quiser. Falha do provedor → 502; demora acima de `TTS_TIMEOUT_SECONDS` (20 s) → 504.
Atenção: o `edge-tts` usa o serviço de leitura em voz alta do Microsoft Edge sem chave, mas
também sem contrato ou garantia de disponibilidade; para produção, considere um provedor com SLA.

**Testes de TTS.** O provedor é simulado (não há internet nos testes). Para validar a síntese real
na sua máquina: `RUN_TTS_INTEGRATION=1 pytest tests/test_tts.py -k real`.
