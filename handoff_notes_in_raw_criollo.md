*** En criollo ***

## Eval

v1 funcionaba bien. Pero 2 de los 12 test cases del golden-set no estaban pasando y tampoco era robusta el evaluation breakdown ya que estaba implicito en formulas. 

v1.1 es tiered y mas robusto, cubre mas coverage y de manera mas explicita. El success rate en el mismo golden-set es de 11/12 vs 10/12, puede parecer marginal el improvement pero desglosado el pass rate es mas bien: v1 72-83% ish vs v1.1 92-96% across 5 categories. 1.1 is as far as I'm going to take it for this challenge.
    - Potential remediations to look into: 
        - [case-11] ReAct observer false positive in _observe_result: 10k > rows = obsrver piensa que fue un aggregation miss. Podría probar anulando el T de 10 k para open-ended queries.

## Dataset 

No quería commit it pero tampoco quería que al correr docker compose up --build en su fin post clone, el db container no arranque por data.csv not present y causara downstream que nlp y ui tampoco arranquen. 

## Docker Compose 

Una vez que clone -> docker compose up --build -> ollama va a tener que pull los modelos. Esto va a hacer que nlp y ui no arranquen solos porque dependen de ollama, van a tener que start manually o docker compose down + up y con los modelos cached arranca todo solo. 

## Ollama y Runtime 

Ollama dentro del container no va a querer correr en GPU a menos que docker este configurado para que lo haga. Asi que por default Ollama container va a tratar de hablar con Ollama host y no con Ollama container, if possible, para hacer uso del GPU. CPU como fallback pero esto x2-3 el runtime. 
***Los modelos auto-pull in-container only. Si el host-probe conecta a Ollama host, los modelos tienen que estar ahi tambien sino tira un 404. Asi que hay que correr un ollama pull por separado.***

## Fully-Local

Inferencias corren via Ollama con dos modelos task-specific:
    - SQL: qwen2.5-coder:14b
    - Synthesis: qwen3:32b
    - Wall-clock time: 3-7 mins para ui queries - 7-24 mins para eval set con llm-as-judge on top.

***Quiere decir algo como 30gb de espacio requerido y 20 gigs de RAM o VRAM requeridos. Nothing trivial***

## Techniques

- Schema Injection:
    A cada sql generation prompt le inyectamos el CREATE TABLE DDL con column comments, date ranges, sample values, etc. El modelo está entrenado de manera que entiende eso mejor que una descripcion en NL. 

- Few-shots: 
    Por query class inyectamos un ejemplo para que el modelo vea la forma *correcta* del query. 

- ReAct:
    SQL execution -> rule-based observer revisa -> if bad, refina con LLM -> repeat | Max steps 4. 
    Rationale: Mitiga SQL valido que retorna la respuesta equivocada. 

- Disambiguation: 
    Pre-step que resuelve lenguaje no especifico antes de generar un query con 0 extra LLM calls. 

## Transparencia

Cada capa es auditable: 
    UI:
        - Narrativa
        - SQL
        - Table
        - Meta (query class, react steps, interpretation)
    
    Operator:
        - Structured JSONL logs emitted per run. 

## Tradeoffs

Bien documentados atravez del repo pero es clave aclarar que la complejidad agregada de DIN-SQL, 4 containers, dos modelos, ReAct, no es accidental y cada decision tiene un rationale y trade-off documentado. 
    - README Architecture Decision Table
    - Decision logs
    - Eval Table con updates v1 -> v1.1
    


