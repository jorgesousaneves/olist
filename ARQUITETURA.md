# Arquitetura e boas práticas

Os princípios que guiam este projeto. Valem para qualquer pipeline de dados; cada um indica onde aparece aqui.

## 1. Arquitetura em camadas (medalhão)

```
fonte ──► bronze (raw) ──► silver (refined) ──► gold (marts) ──► consumo
          como chegou       limpo e tipado        respostas       dashboard, relatório
```

- **Cada camada tem um único trabalho.** A bronze guarda, a silver limpa e a gold responde.
- **O dado só anda para frente.** Uma camada lê apenas da anterior, nunca pula etapas, e nunca escreve na camada de onde lê.
- **A bronze é imutável.** É a fonte da verdade, e qualquer camada acima dela pode ser refeita a partir dela.
- **O consumo só lê da gold.** O dashboard não conhece a raw.

*Aqui:* `raw → refined → marts → app.py`.

## 2. Separação de responsabilidades

- **A regra de negócio mora num lugar só:** o SQL de `sql/marts/`. O Python é encanamento: lê, executa, grava.
- **A apresentação não calcula.** Se a tela precisa de um número novo, falta um mart, não uma conta na tela.
- **Lógica e interface ficam separadas.** `painel.py` serve o Streamlit (`app.py`) e o HTML (`relatorio.py`), porque não depende de nenhum dos dois.

## 3. Reprodutibilidade

- **Tudo é código versionado.** Nada depende de um passo manual ou de uma consulta esquecida no notebook.
- **O ambiente é travado.** O `uv.lock` garante as mesmas versões em qualquer máquina.
- **O resultado é descartável.** O banco não vai para o git: apague e recrie com três comandos.
- **O resultado é determinístico.** Rodar duas vezes dá o mesmo resultado, sem ordem sorteada nem ids aleatórios.

## 4. Idempotência

- **Rodar N vezes = rodar 1 vez.** O resultado é recriado, nunca acrescentado.
- **Limite conhecido:** com uma fonte que muda, a estratégia vira histórico com data de carga na bronze mais a versão mais recente na silver (`ROW_NUMBER() OVER (PARTITION BY chave ORDER BY data_carga DESC)`).

## 5. Integridade e falha segura

- **Falhe cedo e alto.** Pare na primeira inconsistência, com mensagem clara. Um erro calado é pior que um erro barulhento.
- **Transação: tudo ou nada.** Uma falha no meio nunca deixa uma camada pela metade.
- **Se uma etapa falha, a anterior segue de pé.** O consumidor continua vendo o dado de ontem, e não um dado errado hoje.
- **Nunca decida em silêncio.** Na dúvida, pare e mostre: não escolha, não preencha, não descarte.

## 6. Observabilidade

- **Cada etapa mostra o que fez:** linhas que entraram, linhas que saíram, o que foi descartado e por quê.
- **A contagem vem do destino**, lida do banco depois de gravar, e não do que foi lido.
- **Conferências cruzadas.** Dois caminhos independentes têm que chegar ao mesmo total (receita por mês = receita por categoria).

## 7. Qualidade em duas frentes

| | Testa | Roda quando |
|---|---|---|
| **Teste unitário** | O **código**, com dado inventado | O código muda |
| **Qualidade de dados** | O **dado**, com regras (chave única, domínio, não vazio) | O dado chega |

Um pipeline sério tem os dois, porque cada um pega o que o outro não pega. *Aqui:* `test/` com pytest e 95% de coverage; as conferências de dado rodam dentro de cada etapa.

## 8. Concorrência e acesso

- **Quem só lê abre em somente leitura**, e a trava fica na ferramenta, não na boa vontade.
- **Um escritor por vez**, com conexão aberta e fechada a cada uso, nunca presa.
- **Menor privilégio:** a IA acessa o banco por MCP em somente leitura. Quem escreve é o pipeline.

## 9. Documentação como artefato

- **Specs versionadas junto do código** (`specs/`), com o motivo de cada decisão.
- **Critérios de aceite mensuráveis**, que viram testes.
- **README que leva do zero ao resultado** só com comandos.

## 10. Estrutura do repositório

```
olist/
├── raw/              dados de origem (imutáveis)
├── pipeline/         as etapas: ingestão, transformação, marts
├── sql/marts/        a regra de negócio, um arquivo por indicador
├── specs/            as decisões e os motivos
├── test/             testes unitários
├── painel.py         lógica de apresentação
├── app.py            interface (Streamlit)
├── relatorio.py      interface (HTML)
├── pyproject.toml    dependências
├── uv.lock           versões travadas
├── .gitignore        o que não vai para o git (banco, cache, .venv)
└── README.md         como rodar e por quê
```
