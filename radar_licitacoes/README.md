# Radar de licitações de facilities

Lista os pregões eletrônicos com proposta aberta no **PNCP** (Portal Nacional de Contratações Públicas, Lei 14.133/2021) que são de manutenção predial, conservação e limpeza, e gera um relatório em Markdown e uma planilha CSV.

```bash
python radar.py --uf MG --dias 30
```

Só biblioteca padrão do Python (3.10+). Não precisa de chave, login nem navegador.

## Por que existe

Em 2022 meu primeiro script com esse objetivo abria o portal de compras de uma empresa com Selenium, clicava na lista e lia a tabela HTML. Funcionou até a página mudar. Hoje toda contratação pública pela Lei 14.133 é publicada no PNCP, que tem uma API de consulta aberta. A versão nova lê a fonte oficial, sem automação de tela.

## Como decide o que é de facilities

A regra fica no código, e cada ponto vem com o motivo:

| Sinal no objeto | Pontos |
|---|---|
| Termo de uma categoria de interesse (ex.: "manutenção predial", "PMOC", "limpeza", "asseio") | +3 por categoria |
| "Manutenção preventiva/corretiva" **com** contexto de edificação ("predial", "instalações", "sede", "hidráulica"...) | +3 |
| Serviço continuado ("prestação de serviço", "dedicação exclusiva", "mão de obra") | +2 |
| Sinal de que não é facilities ("aquisição", "limpeza urbana", "estradas vicinais", "viaturas", "impressoras") | −3 |

Quem fica com zero ou menos sai do relatório. "Manutenção preventiva e corretiva" sozinho não conta: no PNCP esse texto aparece tanto para prédio quanto para viatura, impressora e equipamento médico. O texto é comparado sem acento e só no início de palavra, para "poda" não casar dentro de outra palavra.

**Perfil padrão:** manutenção predial e seus sistemas (climatização, elétrica, combate a incêndio), conservação e limpeza, vigilância e portaria, e jardinagem. Elevadores está pronto, mas desligado:

```bash
python radar.py --uf MG SP --categorias manutencao limpeza
python radar.py --uf MG --todas
```

## Saída

- `saida/radar_MG_AAAA-MM-DD.md`: resumo por categoria, o que encerra em até 7 dias e a lista completa por pontuação, com link para o edital no PNCP.
- `saida/radar_MG_AAAA-MM-DD.csv`: separado por `;` e com BOM, para abrir direto no Excel. Traz o motivo de cada ponto.

## Leitura guardada

A resposta bruta da API fica em `saida/pncp_<UF>_..._<data>.json`. Rodar de novo no mesmo dia, para testar uma regra nova, não consulta o PNCP outra vez. Use `--atualizar` para forçar.

## Robustez

A API pública limita a taxa (HTTP 429) e às vezes responde sem corpo. O radar espera 1 s entre páginas, tenta de novo com espera crescente e respeita o `Retry-After`. Itens repetidos entre páginas são removidos pelo número de controle do PNCP.

## Testes

```bash
python -m unittest -v test_radar
```

Os testes cobrem classificação, termos negativos, deduplicação, ordenação, descarte de propostas já encerradas e formatação em R$, sem chamar a rede.

## Limites

- A classificação só lê o **objeto** da contratação. Um edital mal descrito escapa; para ler o edital inteiro é preciso outra ferramenta.
- O valor estimado pode vir zerado quando o órgão o mantém sigiloso.
- O padrão é pregão eletrônico (`--modalidade 6`). Outras modalidades usam outros códigos do PNCP.
