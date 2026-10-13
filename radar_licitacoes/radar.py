"""Radar de licitações de facilities a partir da API pública do PNCP.

Lê as contratações com proposta aberta no Portal Nacional de Contratações
Públicas (Lei 14.133/2021), classifica o objeto por categoria de serviço com
regras explícitas e gera um relatório em Markdown e um CSV.

Só biblioteca padrão. Sem login, sem CAPTCHA, sem raspagem de página: a API
de consulta do PNCP é pública e documentada.

Uso:
    python radar.py --uf MG --dias 30
    python radar.py --uf MG SP --categorias manutencao limpeza --saida saida/
    python radar.py --uf MG --todas
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

API = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
PAGINA_MAX = 50  # limite aceito pela API
PREGAO_ELETRONICO = 6

# Categoria -> termos que indicam o serviço. Casam com o objeto já sem acento
# e em minúsculas, por palavra inteira ou início de palavra.
CATEGORIAS: dict[str, list[str]] = {
    "manutencao": [
        "manutencao predial", "manutencao de edificac", "manutencao de imove", "manutencao das instalacoes",
        "manutencao de instalacoes", "manutencao civil", "conservacao predial", "pmoc",
        "manutencao preventiva e corretiva predial", "facilities",
    ],
    "climatizacao": ["ar condicionado", "ar-condicionado", "climatizacao", "refrigeracao", "chiller", "hvac"],
    "eletrica": ["subestac", "instalacoes eletricas", "grupo gerador", "grupos geradores", "spda", "nobreak", "cabine primaria"],
    "incendio": ["combate a incendio", "prevencao e combate", "extintor", "hidrante", "spci", "alarme de incendio"],
    "limpeza": ["limpeza", "asseio", "conservacao", "higienizacao"],
    "vigilancia": [
        "vigilancia patrimonial", "vigilancia armada", "vigilancia desarmada", "vigilancia ostensiva",
        "vigilancia diurna", "vigilancia noturna", "servicos de vigilancia", "servico de vigilancia",
        "vigilancia eletronica", "vigilante", "portaria", "porteiro", "recepcionista", "servicos de recepcao",
    ],
    "elevadores": ["elevador", "escada rolante", "plataforma elevatoria"],
    "jardinagem": ["jardinagem", "rocada", "paisagismo", "poda"],
}

# "Manutenção" sozinho serve para veículo, impressora ou equipamento médico.
# Só conta como predial se o objeto falar de edificação.
MANUTENCAO_GENERICA = ["manutencao"]
CONTEXTO_PREDIAL = [
    "predi", "edific", "imove", "instalacoes", "sede", "unidades administrativas", "escolas",
    "hidraul", "eletrica", "civil", "telhado", "cobertura", "alvenaria", "pintura",
]

# Domínio errado: o termo da categoria aparece, mas o serviço não é de
# facilities predial (limpeza urbana, vigilância sanitária, manutenção de
# viatura...). Excluem o item e o motivo fica registrado.
EXCLUI = [
    "limpeza urbana", "asseio urbano", "coleta de", "residuos solidos", "lixo", "lixao", "fossa",
    "boca de lobo", "corregos", "canais", "terreno", "rodovi", "estrada", "vias publicas", "vicinais",
    "patrolamento", "pavimentacao", "piscina", "demolicao", "pocos",
    "viatura", "veicul", "frota", "maquinas", "caminh", "impressao", "impressora", "informatica",
    "computador", "software", "licenca", "odontolog", "equipamentos medic", "hospitalar", "medicament",
    "vigilancia sanitaria", "vigilancia em saude", "vigilancia epidemiolog", "vigilancia ambiental",
    "zoonose", "telemedicina", "veterinari", "restauro", "acervo", "coffee",
    "esgoto", "drenagem", "tapa-buraco", "cbuq", "perfuracao",
    "evento", "sonorizacao", "tendas", "palco",
]

# Compra de bem, não serviço: fala em aquisição, fornecimento ou material e
# não traz nenhuma palavra de serviço. "Serviços de limpeza com fornecimento
# de materiais" continua valendo; "fornecimento de materiais de limpeza", não.
BEM = ["aquisic", "fornecimento", "compra", "materia", "generos", "aparelhos", "equipamentos", "pecas"]
PALAVRAS_DE_SERVICO = ["servic", "mao de obra", "postos de trabalho"]

# Sinal fraco: serviço misturado com compra. Tira pontos, não exclui.
ATENCAO = ["aquisic"]

# Perfil padrão: empresa de facilities que faz manutenção predial (com seus
# sistemas: climatização, elétrica, incêndio), conservação e limpeza,
# vigilância e portaria, e jardinagem. Elevadores fica disponível com --categorias.
PERFIL_FACILITIES = ["manutencao", "climatizacao", "eletrica", "incendio", "limpeza", "vigilancia", "jardinagem"]

SERVICO = ["prestacao de servico", "servicos continuados", "servico continuado", "mao de obra", "dedicacao exclusiva"]


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e com espaços simples, para casar termos de forma estável."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _casa(termo: str, texto: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(termo), texto) is not None


@dataclass
class Classificacao:
    categorias: list[str]
    pontos: int
    motivos: list[str] = field(default_factory=list)


def classificar(objeto: str) -> Classificacao:
    """Regra no código: cada ponto vem de um termo encontrado e fica no motivo."""
    texto = normalizar(objeto)
    categorias, motivos, pontos = [], [], 0
    for cat, termos in CATEGORIAS.items():
        achados = [t for t in termos if _casa(t, texto)]
        if achados:
            categorias.append(cat)
            pontos += 3
            motivos.append(f"{cat}: {achados[0]}")
    if "manutencao" not in categorias:
        generica = next((t for t in MANUTENCAO_GENERICA if _casa(t, texto)), None)
        contexto = next((t for t in CONTEXTO_PREDIAL if _casa(t, texto)), None)
        if generica and contexto:
            categorias.insert(0, "manutencao")
            pontos += 3
            motivos.insert(0, f"manutencao: {generica} + {contexto}")
    if not categorias:
        return Classificacao([], 0, [])
    if any(_casa(t, texto) for t in SERVICO):
        pontos += 2
        motivos.append("serviço continuado")
    fora = next((t for t in EXCLUI if _casa(t, texto)), None)
    if not fora and any(_casa(t, texto) for t in BEM) and not any(_casa(t, texto) for t in PALAVRAS_DE_SERVICO):
        fora = "compra de bem"
    if fora:
        motivos.append(f"fora: {fora}")
        return Classificacao(categorias, 0, motivos)
    atencao = next((t for t in ATENCAO if _casa(t, texto)), None)
    if atencao:
        pontos -= 3
        motivos.append(f"atenção: {atencao}")
    return Classificacao(categorias, pontos, motivos)


def _get_json(url: str, tentativas: int = 6) -> dict:
    """GET com backoff exponencial: a API do PNCP oscila, limita a taxa (429) e às vezes responde 204 sem corpo."""
    espera = 5.0
    for n in range(1, tentativas + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "radar-licitacoes/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                corpo = resp.read()
                return json.loads(corpo) if corpo else {"data": [], "totalPaginas": 0}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
            if isinstance(erro, urllib.error.HTTPError) and erro.code < 500 and erro.code != 429:
                raise
            if n == tentativas:
                raise
            pausa = espera
            if isinstance(erro, urllib.error.HTTPError) and erro.headers.get("Retry-After", "").isdigit():
                pausa = max(pausa, float(erro.headers["Retry-After"]))
            print(f"  tentativa {n} falhou ({erro}); nova tentativa em {pausa:.0f} s", file=sys.stderr)
            time.sleep(pausa)
            espera *= 2
    raise RuntimeError("inalcançável")


def buscar(uf: str, data_final: date, modalidade: int, max_paginas: int) -> list[dict]:
    """Todas as contratações com proposta aberta até data_final na UF, página a página."""
    itens, pagina, total = [], 1, 1
    while pagina <= min(total, max_paginas):
        params = {
            "dataFinal": data_final.strftime("%Y%m%d"),
            "codigoModalidadeContratacao": modalidade,
            "uf": uf,
            "pagina": pagina,
            "tamanhoPagina": PAGINA_MAX,
        }
        dados = _get_json(f"{API}?{urllib.parse.urlencode(params)}")
        total = dados.get("totalPaginas") or 0
        itens.extend(dados.get("data") or [])
        print(f"  {uf}: página {pagina}/{total}", file=sys.stderr)
        pagina += 1
        time.sleep(1.0)  # a API pública limita a taxa; 1 s por página evita o 429
    return itens


def _data(valor: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(valor) if valor else None
    except ValueError:
        return None


ANTECEDENCIA_PADRAO = 3  # dias: com menos que isso não dá tempo de montar a proposta


def montar_linhas(itens: list[dict], hoje: date, filtro: set[str] | None, antecedencia: int = ANTECEDENCIA_PADRAO) -> list[dict]:
    linhas, vistos = [], set()
    for it in itens:
        controle = it.get("numeroControlePNCP")
        if controle in vistos:
            continue
        vistos.add(controle)
        c = classificar(it.get("objetoCompra", ""))
        if not c.categorias or (filtro and not filtro.intersection(c.categorias)):
            continue
        if c.pontos <= 0:  # excluído (compra de bem, limpeza urbana, viatura...) ou zerado por atenção
            continue
        fim = _data(it.get("dataEncerramentoProposta"))
        dias = (fim.date() - hoje).days if fim else None
        if dias is None or dias < antecedencia:  # já encerrou, não tem data ou não dá tempo
            continue
        unidade = it.get("unidadeOrgao") or {}
        ano, seq = it.get("anoCompra"), it.get("sequencialCompra")
        cnpj = (it.get("orgaoEntidade") or {}).get("cnpj", "")
        linhas.append({
            "pontos": c.pontos,
            "categorias": ", ".join(c.categorias),
            "motivo": "; ".join(c.motivos),
            "encerra": fim.strftime("%d/%m/%Y %H:%M") if fim else "",
            "encerra_iso": fim.isoformat() if fim else "",
            "dias": dias,
            "valor_estimado": it.get("valorTotalEstimado") or 0.0,
            "orgao": (it.get("orgaoEntidade") or {}).get("razaoSocial", ""),
            "municipio": f"{unidade.get('municipioNome', '')}/{unidade.get('ufSigla', '')}",
            "objeto": re.sub(r"\s+", " ", it.get("objetoCompra", "")).strip(),
            "controle_pncp": controle,
            "link": f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if cnpj and ano and seq else "",
        })
    # Mais pontos primeiro; no empate, o que encerra antes.
    linhas.sort(key=lambda l: (-l["pontos"], l["dias"] if l["dias"] is not None else 999))
    return linhas


def reais(valor: float) -> str:
    if not valor:
        return "sigiloso ou não informado"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def escrever_csv(linhas: list[dict], caminho: Path) -> None:
    campos = ["pontos", "categorias", "encerra", "dias", "valor_estimado", "orgao", "municipio", "objeto", "motivo", "controle_pncp", "link"]
    with caminho.open("w", newline="", encoding="utf-8-sig") as f:  # BOM: o Excel abre com acento certo
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def escrever_md(linhas: list[dict], caminho: Path, ufs: list[str], lidos: int, hoje: date, filtro: set[str] | None = None) -> None:
    urgentes = [l for l in linhas if l["dias"] is not None and l["dias"] <= 7]
    por_cat: dict[str, int] = {}
    for l in linhas:
        for c in l["categorias"].split(", "):
            if filtro is None or c in filtro:
                por_cat[c] = por_cat.get(c, 0) + 1
    md = [
        f"# Radar de licitações · {', '.join(ufs)} · {hoje.strftime('%d/%m/%Y')}",
        "",
        f"{lidos} contratações com proposta aberta lidas no PNCP; **{len(linhas)}** são de facilities; "
        f"**{len(urgentes)}** encerram em até 7 dias.",
        "",
        "| Categoria | Editais |",
        "|---|---|",
        *[f"| {c} | {n} |" for c, n in sorted(por_cat.items(), key=lambda x: -x[1])],
        "",
        "## Encerram em até 7 dias",
        "",
    ]
    md += _tabela(urgentes) if urgentes else ["Nenhum.", ""]
    md += ["## Todos, por pontuação", ""] + _tabela(linhas)
    md += ["---", "Pontuação: +3 por categoria encontrada, +2 se é serviço continuado, −3 se mistura serviço com aquisição. Compra de bem e serviço de outro domínio (limpeza urbana, vigilância sanitária, viatura) saem do relatório. O motivo de cada ponto está no CSV."]
    caminho.write_text("\n".join(md), encoding="utf-8")


def escrever_json(linhas: list[dict], caminho: Path, ufs: list[str], lidos: int, hoje: date) -> None:
    """Resumo para publicar (ex.: numa página web): só dado público do PNCP."""
    urgentes = sum(1 for l in linhas if l["dias"] is not None and l["dias"] <= 7)
    dados = {
        "rodada": hoje.isoformat(),
        "ufs": ufs,
        "lidos": lidos,
        "selecionados": len(linhas),
        "encerram_7_dias": urgentes,
        "itens": [
            {k: l[k] for k in ("pontos", "categorias", "motivo", "encerra_iso", "valor_estimado", "orgao", "municipio", "objeto", "link")}
            for l in linhas
        ],
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def _tabela(linhas: list[dict]) -> list[str]:
    out = ["| Pts | Encerra | Valor estimado | Órgão | Objeto |", "|---|---|---|---|---|"]
    for l in linhas:
        objeto = l["objeto"][:140] + ("…" if len(l["objeto"]) > 140 else "")
        objeto = objeto.replace("|", "/")
        link = f"[{objeto}]({l['link']})" if l["link"] else objeto
        out.append(f"| {l['pontos']} | {l['encerra']} ({l['dias']} d) | {reais(l['valor_estimado'])} | {l['orgao']} · {l['municipio']} | {link} |")
    return out + [""]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Radar de licitações de facilities (API pública do PNCP).")
    p.add_argument("--uf", nargs="+", default=["MG"], help="UFs, ex.: MG SP")
    p.add_argument("--dias", type=int, default=30, help="propostas que encerram em até N dias (padrão 30)")
    p.add_argument("--categorias", nargs="*", choices=sorted(CATEGORIAS), default=PERFIL_FACILITIES,
                   help="categorias de interesse (padrão: todas menos elevadores)")
    p.add_argument("--todas", action="store_true", help="todas as categorias, inclusive elevadores")
    p.add_argument("--modalidade", type=int, default=PREGAO_ELETRONICO, help="código da modalidade no PNCP (6 = pregão eletrônico)")
    p.add_argument("--antecedencia", type=int, default=ANTECEDENCIA_PADRAO,
                   help=f"só editais que encerram daqui a pelo menos N dias (padrão {ANTECEDENCIA_PADRAO})")
    p.add_argument("--max-paginas", type=int, default=100, help="teto de páginas por UF")
    p.add_argument("--saida", type=Path, default=Path("saida"), help="pasta do relatório")
    p.add_argument("--json", type=Path, help="também grava um resumo em JSON neste caminho")
    p.add_argument("--atualizar", action="store_true", help="consulta o PNCP de novo mesmo que já exista a leitura de hoje")
    a = p.parse_args(argv)

    hoje = date.today()
    a.saida.mkdir(parents=True, exist_ok=True)
    itens: list[dict] = []
    for uf in (u.upper() for u in a.uf):
        # A leitura bruta do dia fica guardada: mudar a regra e rodar de novo não consulta a API outra vez.
        bruto = a.saida / f"pncp_{uf}_{a.modalidade}_{a.dias}d_{hoje.isoformat()}.json"
        if bruto.exists() and not a.atualizar:
            print(f"  {uf}: usando a leitura de hoje em {bruto.name}", file=sys.stderr)
            itens += json.loads(bruto.read_text(encoding="utf-8"))
            continue
        lidos = buscar(uf, hoje + timedelta(days=a.dias), a.modalidade, a.max_paginas)
        bruto.write_text(json.dumps(lidos, ensure_ascii=False), encoding="utf-8")
        itens += lidos
    filtro = None if a.todas else set(a.categorias)
    linhas = montar_linhas(itens, hoje, filtro, a.antecedencia)

    base = a.saida / f"radar_{'-'.join(u.upper() for u in a.uf)}_{hoje.isoformat()}"
    escrever_csv(linhas, base.with_suffix(".csv"))
    escrever_md(linhas, base.with_suffix(".md"), [u.upper() for u in a.uf], len(itens), hoje, filtro)
    if a.json:
        escrever_json(linhas, a.json, [u.upper() for u in a.uf], len(itens), hoje)
    print(f"{len(itens)} lidos, {len(linhas)} de facilities → {base}.md / .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
