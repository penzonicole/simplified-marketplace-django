from decimal import Decimal
from unittest.mock import patch
from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from .admin import ProdutoAdmin
from .models import Categoria, ItemPedido, Pedido, Produto


class Base(TestCase):
    def setUp(self):
        self.vend1 = User.objects.create_user('vend1', password='x', is_staff=True)
        self.vend2 = User.objects.create_user('vend2', password='x', is_staff=True)
        self.comprador = User.objects.create_user('cliente', password='x')
        self.cat = Categoria.objects.create(nome='Livros')
        self.p1 = Produto.objects.create(
            vendedor=self.vend1, categoria=self.cat,
            nome='Caneta', preco=Decimal('3.50'), estoque=10
        )
        self.p2 = Produto.objects.create(
            vendedor=self.vend2, categoria=self.cat,
            nome='Caderno', preco=Decimal('20.00'), estoque=2
        )

    def add(self, produto, vezes=1):
        for _ in range(vezes):
            self.client.post(reverse('adicionar_carrinho', args=[produto.id]))


class AdminTest(Base):
    def test_vendedor_ve_so_os_proprios_produtos(self):
        ma = ProdutoAdmin(Produto, admin.site)
        req = RequestFactory().get('/admin/loja/produto/')
        req.user = self.vend1
        self.assertEqual(list(ma.get_queryset(req)), [self.p1])
        req.user = self.vend2
        self.assertEqual(list(ma.get_queryset(req)), [self.p2])

    def test_save_model_define_vendedor(self):
        ma = ProdutoAdmin(Produto, admin.site)
        req = RequestFactory().post('/')
        req.user = self.vend1
        novo = Produto(categoria=self.cat, nome='Novo', preco=Decimal('1'), estoque=1)
        ma.save_model(req, novo, None, change=False)
        self.assertEqual(novo.vendedor, self.vend1)


class CarrinhoTest(Base):
    def test_carrinho_funciona_sem_login(self):
        self.add(self.p1, 2)
        self.add(self.p2)
        r = self.client.get(reverse('carrinho'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['total'], Decimal('27.00'))

    def test_adicionar_exige_post(self):
        self.assertEqual(
            self.client.get(reverse('adicionar_carrinho', args=[self.p1.id])).status_code,
            405
        )

    def test_checkout_exige_login(self):
        self.add(self.p1)
        r = self.client.post(reverse('checkout'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)
        self.assertEqual(Pedido.objects.count(), 0)


class CheckoutTest(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.comprador)

    def test_compra_ok_baixa_estoque_e_limpa_carrinho(self):
        self.add(self.p1, 3)
        self.add(self.p2, 1)
        self.client.post(reverse('checkout'))
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.itens.count(), 2)
        self.assertEqual(pedido.total, Decimal('30.50'))
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual((self.p1.estoque, self.p2.estoque), (7, 1))
        self.assertEqual(self.client.session['carrinho'], {})

    def test_sem_estoque_cancela_tudo(self):
        self.add(self.p1, 1)
        self.add(self.p2, 3)  # só há 2
        self.client.post(reverse('checkout'))
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(ItemPedido.objects.count(), 0)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.estoque, 10)
        self.assertTrue(self.client.session['carrinho'])  # carrinho preservado

    def test_atomicidade_erro_no_meio_da_criacao(self):
        self.add(self.p1, 1)
        self.add(self.p2, 1)
        original = ItemPedido.objects.create
        chamadas = {'n': 0}

        def falha_no_segundo(*a, **k):
            chamadas['n'] += 1
            if chamadas['n'] == 2:
                raise RuntimeError('falha forçada')
            return original(*a, **k)

        with patch('loja.views.ItemPedido.objects.create', side_effect=falha_no_segundo):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('checkout'))

        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(ItemPedido.objects.count(), 0)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.estoque, 10)

    def test_preco_historico_nao_muda(self):
        self.add(self.p1, 1)
        self.client.post(reverse('checkout'))
        self.p1.preco = Decimal('99.00')
        self.p1.save()
        self.assertEqual(ItemPedido.objects.get().preco_unitario, Decimal('3.50'))


class APITest(Base):
    def test_leitura_publica(self):
        r = APIClient().get(reverse('api-produtos'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)

    def test_escrita_exige_login(self):
        r = APIClient().post(
            reverse('api-produtos'),
            {'nome': 'X', 'preco': '1', 'estoque': 1, 'categoria': self.cat.id}
        )
        self.assertIn(r.status_code, (401, 403))

    def test_vendedor_automatico(self):
        c = APIClient()
        c.force_authenticate(self.vend1)
        r = c.post(
            reverse('api-produtos'),
            {
                'nome': 'Lápis', 'preco': '2.00', 'estoque': 5,
                'categoria': self.cat.id, 'vendedor': self.vend2.id
            }
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Produto.objects.get(nome='Lápis').vendedor, self.vend1)

    def test_pedido_aninhado_ignora_preco_do_cliente(self):
        c = APIClient()
        c.force_authenticate(self.comprador)
        r = c.post(
            reverse('api-pedidos'),
            {
                'itens': [
                    {'produto': self.p1.id, 'quantidade': 2, 'preco_unitario': '0.01'},
                    {'produto': self.p2.id, 'quantidade': 1}
                ]
            },
            format='json'
        )
        self.assertEqual(r.status_code, 201, r.content)
        itens = {i.produto_id: i for i in ItemPedido.objects.all()}
        self.assertEqual(itens[self.p1.id].preco_unitario, Decimal('3.50'))
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.estoque, 8)

    def test_pedido_sem_estoque_nao_grava_nada(self):
        c = APIClient()
        c.force_authenticate(self.comprador)
        r = c.post(
            reverse('api-pedidos'),
            {
                'itens': [
                    {'produto': self.p1.id, 'quantidade': 1},
                    {'produto': self.p2.id, 'quantidade': 5}
                ]
            },
            format='json'
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Pedido.objects.count(), 0)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.estoque, 10)

    def test_pedido_exige_login(self):
        r = APIClient().post(reverse('api-pedidos'), {'itens': []}, format='json')
        self.assertIn(r.status_code, (401, 403))

    def test_catalogo_pagina_usa_fetch(self):
        r = self.client.get(reverse('catalogo'))
        self.assertContains(r, "fetch('/api/produtos/')")
        self.assertContains(r, 'localStorage')


class LoginTest(Base):
    def test_carrinho_anonimo_mostra_link_de_login(self):
        self.add(self.p1)
        r = self.client.get(reverse('carrinho'))
        self.assertContains(r, 'entre na sua conta')
        self.assertNotContains(r, 'Finalizar compra')

    def test_pagina_de_login_existe_e_carrinho_sobrevive_ao_login(self):
        self.add(self.p1, 2)
        self.assertEqual(self.client.get(reverse('rest_framework:login')).status_code, 200)
        self.client.post(
            reverse('rest_framework:login'),
            {'username': 'cliente', 'password': 'x', 'next': '/carrinho/'}
        )
        r = self.client.get(reverse('carrinho'))
        self.assertContains(r, 'Finalizar compra')
        self.assertEqual(r.context['total'], Decimal('7.00'))


class AdminFluxoTest(Base):
    """Fluxo real no Admin: vendedor com permissões de Produto cadastra e só vê o que é dele."""
    def setUp(self):
        super().setUp()
        perms = Permission.objects.filter(
            content_type__app_label='loja',
            content_type__model='produto'
        )
        self.vend1.user_permissions.set(perms)
        self.vend2.user_permissions.set(perms)

    def test_vendedor_cadastra_e_lista_so_o_proprio(self):
        self.client.force_login(self.vend1)
        r = self.client.get('/admin/loja/produto/add/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'name="vendedor"')
        r = self.client.post('/admin/loja/produto/add/', {
            'categoria': self.cat.id,
            'nome': 'Régua',
            'descricao': '',
            'preco': '4.00',
            'estoque': 7
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Produto.objects.get(nome='Régua').vendedor, self.vend1)
        lista = self.client.get('/admin/loja/produto/')
        self.assertContains(lista, 'Caneta')
        self.assertContains(lista, 'Régua')
        self.assertNotContains(lista, 'Caderno')


class DesafiosExtrasTest(Base):
    def test_filtros_api_categoria_e_preco(self):
        c = APIClient()
        r_cat = c.get(reverse('api-produtos'), {'categoria': self.cat.id, 'preco_max': '10.00'})
        self.assertEqual(r_cat.status_code, 200)
        self.assertEqual(len(r_cat.json()), 1)
        self.assertEqual(r_cat.json()[0]['nome'], 'Caneta')

    def test_avaliacao_apenas_para_quem_comprou(self):
        c = APIClient()
        c.force_authenticate(self.comprador)
        # Tenta avaliar antes de comprar -> deve falhar (400)
        r_sem_compra = c.post(reverse('api-avaliacoes'), {'produto': self.p1.id, 'nota': 5})
        self.assertEqual(r_sem_compra.status_code, 400)

        # Compra o produto e avalia -> deve funcionar (201)
        pedido = Pedido.objects.create(comprador=self.comprador, status='PAGO')
        ItemPedido.objects.create(pedido=pedido, produto=self.p1, quantidade=1, preco_unitario=self.p1.preco)
        r_com_compra = c.post(reverse('api-avaliacoes'), {'produto': self.p1.id, 'nota': 5, 'comentario': 'Ótima!'})
        self.assertEqual(r_com_compra.status_code, 201)

    def test_gateway_pagamento_sandbox(self):
        pedido = Pedido.objects.create(comprador=self.comprador, status='ABERTO')
        ItemPedido.objects.create(pedido=pedido, produto=self.p1, quantidade=2, preco_unitario=self.p1.preco)
        c = APIClient()
        c.force_authenticate(self.comprador)
        r = c.post(reverse('api-pagar-pedido', args=[pedido.id]))
        self.assertEqual(r.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'PAGO')

    def test_painel_vendedor_aggregate_e_sum(self):
        pedido = Pedido.objects.create(comprador=self.comprador, status='PAGO')
        ItemPedido.objects.create(pedido=pedido, produto=self.p1, quantidade=2, preco_unitario=Decimal('3.50'))
        ItemPedido.objects.create(pedido=pedido, produto=self.p2, quantidade=1, preco_unitario=Decimal('20.00'))

        self.client.force_login(self.vend1)
        r = self.client.get(reverse('painel_vendedor'))
        self.assertEqual(r.status_code, 200)
        # vend1 vendeu apenas p1 (2 * 3.50 = 7.00), não vê vendas de vend2
        self.assertEqual(r.context['resumo_geral']['faturamento_total'], Decimal('7.00'))

