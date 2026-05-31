# 🏗️ python-facility-tools

Automações Python para gestão de manutenção predial — geração de documentos, relatórios e utilitários operacionais.

> Desenvolvido por um Coordenador de Manutenção Predial multiescopo para resolver problemas reais de operação.

---

## 🧰 Stack

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=flat&logo=pandas&logoColor=white)
![OpenPyXL](https://img.shields.io/badge/OpenPyXL-217346?style=flat&logo=microsoftexcel&logoColor=white)
![ReportLab](https://img.shields.io/badge/ReportLab-PDF-red?style=flat)
![python-docx](https://img.shields.io/badge/python--docx-DOCX-2B579A?style=flat)

---

## 📂 Estrutura

```
python-facility-tools/
│
├── gerar_relatorio_pdf.py        # Gerador de relatórios em PDF a partir de dados tabulares
├── agendador_tarefas.py          # Agendamento de scripts via Task Scheduler (Windows)
├── check_syntax.py               # Validador de sintaxe para scripts Python em lote
│
├── data/
│   └── exemplo_dados.xlsx        # Planilha de exemplo para testes
│
└── requirements.txt
```

---

## ⚙️ Funcionalidades

### `gerar_relatorio_pdf.py`
- Lê dados de planilha Excel (`.xlsx`)
- Gera relatório PDF formatado com cabeçalho, tabela de dados e rodapé
- Suporta filtragem por período e categoria
- Saída: arquivo `.pdf` com nome baseado na data de geração

### `agendador_tarefas.py`
- Cria tarefas agendadas no Windows Task Scheduler via linha de comando
- Suporta frequências: diária, semanal, mensal
- Log de execução em arquivo `.txt`

### `check_syntax.py`
- Varre uma pasta e valida sintaxe de todos os arquivos `.py`
- Retorna lista de arquivos com erro e linha do problema
- Útil antes de deployar scripts em produção

---

## 🚀 Como usar

### 1. Clonar o repositório

```bash
git clone https://github.com/guihrodriguess/python-facility-tools.git
cd python-facility-tools
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Executar exemplo

```bash
python gerar_relatorio_pdf.py --input data/exemplo_dados.xlsx --output relatorio.pdf
```

---

## 📋 Requisitos

```
pandas>=2.0
openpyxl>=3.1
reportlab>=4.0
python-docx>=1.1
```

---

## 🗂️ Contexto de uso

Scripts desenvolvidos para operação real em contratos de manutenção predial multiescopo:
- Elétrica, hidráulica, civil, HVAC, serralheria
- Gestão de equipes, ordens de serviço, auditorias e relatórios gerenciais

Os scripts neste repositório são versões genéricas e desacopladas dos sistemas internos, adaptadas para uso livre.

---

## 👤 Autor

**Guilherme Rodrigues**  
Coordenador de Manutenção Predial | Power BI | Python

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://linkedin.com/in/guilherme-rodrigues-a532077b/)
[![YouTube](https://img.shields.io/badge/Hypersonic_Gaming-FF0000?style=flat&logo=youtube&logoColor=white)](https://youtube.com/channel/UCkUoJfkhp-WHO6fO4K2NRGA)
[![Instagram](https://img.shields.io/badge/@hypersonicgamming-E4405F?style=flat&logo=instagram&logoColor=white)](https://instagram.com/hypersonicgamming)

---

## 📄 Licença

MIT License — livre para uso, adaptação e distribuição com atribuição.
