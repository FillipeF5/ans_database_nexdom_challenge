# Desafio Técnico NEXDOM — Pipeline ETL Medallion (ANS)

Pipeline de dados utilizando **Python** e **DuckDB** seguindo a arquitetura **Medallion** (`bronze`, `silver` e `gold`) para integrar e analisar dados abertos da Agência Nacional de Saúde Suplementar (**ANS**): cadastro de operadoras (ativas e canceladas), operadoras acreditadas, Índice Geral de Reclamações (**IGR**) e Taxa de Resolutividade (**TR**).

---

## Arquitetura do Projeto

O projeto organiza o processamento em camadas incrementais para separar ingestão bruta, padronização/qualidade e consumo analítico:

* **`bronze`:** ingestão das bases brutas com tratamento de *encoding*, normalização inicial de nomes/estrutura e adição de colunas técnicas de auditoria (`_arquivo_origem` e `_dt_ingestao`).
* **`silver`:** limpeza, tipagem estrita e regras de negócio baseadas nos dicionários oficiais da ANS, com validação de integridade, cobertura de chaves e ausência de duplicidade de grão.
* **`gold`:** modelagem analítica final voltada às perguntas de negócio, às análises obrigatórias do desafio e ao consumo em ferramentas de BI (como o Power BI).

Estrutura esperada do repositório:

```text
.
├── .github/workflows/       # Automação de checagens/CI (opcional)
├── .vscode/
│   └── settings.json        # Configurações de ambiente / caminhos relativos
├── data/                    # Bases brutas e saídas locais (ignoradas no Git)
├── src/
│   └── etl/
│       ├── config.py        # Caminhos e configurações do banco DuckDB
│       ├── 01_bronze.py     # Ingestão para o schema bronze
│       ├── 02_silver.py     # Limpeza, tipagem e regras para o schema silver
│       └── 03_gold.py       # Tabelas/visões analíticas e exportações da gold
├── .gitignore
└── README.md