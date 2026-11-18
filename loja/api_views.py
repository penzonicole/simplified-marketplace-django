import uuid
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Avaliacao, Pedido, Produto
from .serializers import AvaliacaoSerializer, PedidoSerializer, ProdutoSerializer


class ProdutoListCreateView(generics.ListCreateAPIView):
    """GET é público com filtros (?categoria=, ?preco_min=, ?preco_max=); POST exige login."""
    serializer_class = ProdutoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Produto.objects.select_related('categoria').order_by('nome')
        categoria = self.request.query_params.get('categoria')
        preco_min = self.request.query_params.get('preco_min')
        preco_max = self.request.query_params.get('preco_max')

        if categoria:
            qs = qs.filter(categoria_id=categoria)
        try:
            if preco_min:
                qs = qs.filter(preco__gte=Decimal(preco_min))
            if preco_max:
                qs = qs.filter(preco__lte=Decimal(preco_max))
        except InvalidOperation:
            pass
        return qs

    def perform_create(self, serializer):
        serializer.save(vendedor=self.request.user)


class PedidoCreateView(generics.CreateAPIView):
    queryset = Pedido.objects.all()
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]


class AvaliacaoListCreateView(generics.ListCreateAPIView):
    queryset = Avaliacao.objects.select_related('comprador', 'produto').order_by('-criado_em')
    serializer_class = AvaliacaoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(comprador=self.request.user)


class PagamentoSandboxView(APIView):
    """Simula confirmação de pagamento via gateway sandbox antes de marcar pedido como PAGO."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pedido_id):
        pedido = get_object_or_404(Pedido, pk=pedido_id, comprador=request.user)
        if pedido.status != 'ABERTO':
            return Response(
                {'erro': f'Pedido #{pedido.pk} não está aberto (status atual: {pedido.status}).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not getattr(settings, 'PAYMENT_SANDBOX_KEY', '').startswith('sk_test_'):
            return Response(
                {'erro': 'Chave sandbox de pagamento não configurada.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        pedido.status = 'PAGO'
        pedido.save(update_fields=['status'])

        return Response({
            'mensagem': f'Pagamento aprovado em ambiente sandbox para Pedido #{pedido.pk}.',
            'transacao_id': f'sandbox_{uuid.uuid4().hex[:12]}',
            'status': pedido.status,
            'total_pago': str(pedido.total)
        }, status=status.HTTP_200_OK)