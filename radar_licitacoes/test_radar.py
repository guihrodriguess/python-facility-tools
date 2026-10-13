"""Testes do classificador e da montagem do relatório, sem rede."""

import unittest
from datetime import date

from radar import classificar, montar_linhas, normalizar, reais


class TestClassificar(unittest.TestCase):
    def test_normaliza_acento_e_espaco(self):
        self.assertEqual(normalizar("  MANUTENÇÃO   Predial "), "manutencao predial")

    def test_manutencao_servico_continuado(self):
        c = classificar("Contratação de empresa para prestação de serviços continuados de manutenção predial preventiva e corretiva")
        self.assertIn("manutencao", c.categorias)
        self.assertEqual(c.pontos, 5)

    def test_varias_categorias_somam(self):
        c = classificar("Serviços de limpeza, conservação e vigilância patrimonial")
        self.assertEqual(sorted(c.categorias), ["limpeza", "vigilancia"])
        self.assertEqual(c.pontos, 6)

    def test_compra_de_material_perde_pontos(self):
        c = classificar("Aquisição de material de limpeza para as escolas municipais")
        self.assertIn("limpeza", c.categorias)
        self.assertEqual(c.pontos, 0)
        self.assertTrue(any(m.startswith("fora:") for m in c.motivos))

    def test_limpeza_urbana_e_estrada_perdem_pontos(self):
        self.assertLessEqual(classificar("Serviços de limpeza urbana e coleta de resíduos").pontos, 0)
        self.assertLessEqual(classificar("Conservação de estradas vicinais").pontos, 0)

    def test_manutencao_generica_exige_contexto_predial(self):
        self.assertEqual(classificar("Manutenção preventiva e corretiva de viaturas").categorias, [])
        self.assertEqual(classificar("Serviços de manutenção preventiva e corretiva em impressoras").categorias, [])
        c = classificar("Manutenção preventiva e corretiva das instalações hidráulicas da sede")
        self.assertEqual(c.categorias, ["manutencao"])
        self.assertIn("+", c.motivos[0])

    def test_servico_com_fornecimento_de_material_nao_perde_pontos(self):
        c = classificar("Serviços continuados de limpeza e conservação, com fornecimento de materiais e equipamentos")
        self.assertEqual(c.pontos, 5)

    def test_compra_depois_de_registro_de_precos_e_portal(self):
        for objeto in [
            "Registro de preços para futura e eventual aquisição de aparelhos de ar condicionado",
            "[Portal de Compras Públicas] - Fornecimento de extintores de incêndio",
        ]:
            self.assertEqual(classificar(objeto).pontos, 0, objeto)

    def test_vigilancia_sanitaria_nao_e_vigilancia_patrimonial(self):
        self.assertEqual(classificar("Insumos para as ações de vigilância sanitária e zoonoses").pontos, 0)
        self.assertIn("vigilancia", classificar("Serviços de vigilância patrimonial desarmada").categorias)

    def test_insumos_e_pecas_em_contrato_de_servico_nao_perdem_pontos(self):
        c = classificar("Serviços continuados de manutenção de ar-condicionado, com fornecimento de peças e insumos")
        self.assertEqual(c.pontos, 5)

    def test_material_de_limpeza_sem_servico_sai(self):
        self.assertEqual(classificar("Registro de preços de materiais de limpeza e utensílios domésticos").pontos, 0)

    def test_material_para_manutencao_predial_e_compra(self):
        self.assertEqual(classificar("Aquisição de materiais elétricos destinados à manutenção predial").pontos, 0)

    def test_manutencao_de_edificacoes_publicas(self):
        c = classificar("Serviços contínuos de manutenção e adequação das edificações públicas")
        self.assertIn("manutencao", c.categorias)

    def test_fora_do_escopo(self):
        self.assertEqual(classificar("Locação de brinquedos infláveis para eventos").categorias, [])

    def test_casa_inicio_de_palavra_nao_meio(self):
        # "poda" não pode casar dentro de "apodarecer"; "pmoc" casa como palavra
        self.assertEqual(classificar("material para apodarecer").categorias, [])
        self.assertIn("manutencao", classificar("Execução do PMOC das unidades").categorias)


class TestLinhas(unittest.TestCase):
    def _item(self, controle, objeto, fim):
        return {
            "numeroControlePNCP": controle, "objetoCompra": objeto, "dataEncerramentoProposta": fim,
            "valorTotalEstimado": 1000.0, "anoCompra": 2026, "sequencialCompra": 7,
            "orgaoEntidade": {"cnpj": "00000000000191", "razaoSocial": "ÓRGÃO TESTE"},
            "unidadeOrgao": {"municipioNome": "Cidade", "ufSigla": "MG"},
        }

    def test_ordena_dedup_e_descarta_vencido(self):
        hoje = date(2026, 10, 12)
        itens = [
            self._item("a", "Serviço de limpeza", "2026-10-30T09:00:00"),
            self._item("b", "Prestação de serviço continuado de manutenção predial", "2026-10-20T09:00:00"),
            self._item("b", "Prestação de serviço continuado de manutenção predial", "2026-10-20T09:00:00"),
            self._item("c", "Serviço de vigilância", "2026-10-01T09:00:00"),  # já encerrou
            self._item("d", "Compra de computadores", "2026-10-20T09:00:00"),
            self._item("e", "Aquisição de material de limpeza", "2026-10-20T09:00:00"),  # zera e sai
        ]
        linhas = montar_linhas(itens, hoje, None)
        self.assertEqual([l["controle_pncp"] for l in linhas], ["b", "a"])
        self.assertEqual(linhas[0]["dias"], 8)
        self.assertEqual(linhas[0]["link"], "https://pncp.gov.br/app/editais/00000000000191/2026/7")

    def test_filtro_de_categoria(self):
        hoje = date(2026, 10, 12)
        itens = [self._item("a", "Serviço de limpeza", "2026-10-30T09:00:00")]
        self.assertEqual(montar_linhas(itens, hoje, {"vigilancia"}), [])

    def test_reais(self):
        self.assertEqual(reais(1234567.8), "R$ 1.234.567,80")
        self.assertEqual(reais(0), "sigiloso ou não informado")


if __name__ == "__main__":
    unittest.main()
