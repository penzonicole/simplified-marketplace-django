from django.db import transaction
from rest_framework import serializers
from .models import Avaliacao, ItemPedido, Pedido, Produto

class AvaliacaoSerializer(serializers.ModelSerializer):
    comprador_nome = serializers.CharField(source='comprador.username', read_only=True)

    class Meta:
        model = Avaliacao
        fields = ['id', 'produto', 'comprador_nome', 'nota', 'comentario', 'criado_em']
        read_only_fields = ['comprador_nome', 'criado_em']

    def validate(self, attrs):
        comprador = self.context['request'].user
        produto = attrs['produto']
        comprou = ItemPedido.objects.filter(
            pedido__comprador=comprador,
            produto=produto
        ).exclude(pedido__status='CANCELADO').exists()

        if not comprou:
            raise serializers.ValidationError(
                'Apenas clientes que compraram este produto podem avaliá-lo.'
            )
        if Avaliacao.objects.filter(comprador=comprador, produto=produto).exists():
            raise serializers.ValidationError('Você já avaliou este produto.')
        return attrs


class ProdutoSerializer(serializers.ModelSerializer):
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True)

    class Meta:
        model = Produto
        fields = [
            'id', 'nome', 'descricao', 'preco', 'estoque',
            'categoria', 'categoria_nome', 'vendedor'
        ]
        read_only_fields = ['vendedor']


class ItemPedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPedido
        fields = ['produto', 'quantidade', 'preco_unitario']
        # O preço NUNCA vem do cliente: é copiado do banco.
        read_only_fields = ['preco_unitario']


class PedidoSerializer(serializers.ModelSerializer):
    itens = ItemPedidoSerializer(many=True)

    class Meta:
        model = Pedido
        fields = ['id', 'status', 'criado_em', 'itens']
        read_only_fields = ['status', 'criado_em']

    def validate_itens(self, itens):
        if not itens:
            raise serializers.ValidationError('O pedido precisa ter ao menos um item.')
        for item in itens:
            if item['quantidade'] < 1:
                raise serializers.ValidationError('A quantidade mínima é 1.')
        return itens

    def create(self, validated_data):
        # O DRF não cria objetos aninhados sozinho: fazemos aqui, em uma transação.
        itens_data = validated_data.pop('itens')
        comprador = self.context['request'].user

        with transaction.atomic():
            pedido = Pedido.objects.create(comprador=comprador, **validated_data)
            for item in itens_data:
                produto = Produto.objects.select_for_update().get(pk=item['produto'].pk)
                if produto.estoque < item['quantidade']:
                    raise serializers.ValidationError(
                        {'itens': f'Estoque insuficiente para "{produto.nome}".'}
                    )
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    quantidade=item['quantidade'],
                    preco_unitario=produto.preco
                )
                produto.estoque -= item['quantidade']
                produto.save()

        return pedido