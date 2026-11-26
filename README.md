# Desafio Técnico NEXDOM — Pipeline ETL Medallion (ANS)

Pipeline de dados utilizando **Python** e **DuckDB** seguindo a arquitetura **Medallion** (`bronze`, `silver` e `gold`) para integrar e analisar dados abertos da Agência Nacional de Saúde Suplementar (**ANS**): cadastro de operadoras (ativas e canceladas), operadoras acreditadas, Índice Geral de Reclamações (**IGR**) e Taxa de Resolutividade (**TR**).

---

## Decisão de Arquitetura e Evolução para Produção

* **Adequação ao escopo do desafio:** como o volume de dados da ANS é moderado (não configura cenário de *Big Data*), o projeto tem caráter temporário/avaliativo e o prazo é curto, optou-se por uma stack leve, local e reprodutível com **Python + DuckDB** e exportação analítica para **Power BI**, evitando o custo de configurar infraestrutura de servidor ou ferramentas pesadas apenas para o teste.
* **Aderência conceitual ao fluxo de ETL:** embora o ambiente produtivo de referência envolva extração, *staging*/transformação em banco relacional e camada analítica/BI, a separação em camadas (`bronze` → `silver` → `gold`) mantém a mesma lógica de *staging*, padronização e preparação de dados analíticos antes da visualização.
* **Limitações do modelo local e como escalaria em produção:** por ser um banco *embedded* em arquivo local (ignorado no Git), não expõe conexão remota compartilhada por padrão nem entrega o `.duckdb` pronto via repositório — quem executa roda os scripts localmente. Em um ambiente contínuo de produção, o mesmo desenho lógico pode ser conectado a um banco em servidor (como PostgreSQL), agendado em orquestrador/rotina automatizada e plugado à camada de BI sem reescrever as regras de negócio.

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