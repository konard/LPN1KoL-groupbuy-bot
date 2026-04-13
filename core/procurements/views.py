"""
Views for Procurements API
"""
import logging
import uuid as uuid_lib

from django.db import transaction as db_transaction
from django.utils import timezone
from django.db.models import Count
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Category, Procurement, Participant, SupplierVote, VoteCloseRequest, SupplierDocumentJob
from .serializers import (
    CategorySerializer, ProcurementListSerializer, ProcurementDetailSerializer,
    ProcurementCreateSerializer, ParticipantSerializer, JoinProcurementSerializer,
    SupplierVoteSerializer, CastVoteSerializer, AddParticipantSerializer,
    InviteUserSerializer,
)

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing categories"""
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        parent = self.request.query_params.get('parent')
        if parent:
            queryset = queryset.filter(parent_id=parent)
        elif parent == '':
            queryset = queryset.filter(parent__isnull=True)
        return queryset


class ProcurementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing procurements.

    Endpoints:
    - GET /api/procurements/ - list all procurements (with filters)
    - POST /api/procurements/ - create new procurement
    - GET /api/procurements/{id}/ - get procurement details
    - PUT /api/procurements/{id}/ - update procurement
    - DELETE /api/procurements/{id}/ - delete procurement
    - GET /api/procurements/{id}/participants/ - list participants
    - POST /api/procurements/{id}/join/ - join a procurement
    - POST /api/procurements/{id}/leave/ - leave a procurement
    - GET /api/procurements/user/{user_id}/ - get user's procurements
    - POST /api/procurements/{id}/check_access/ - check user access
    - POST /api/procurements/{id}/update_status/ - update status
    - POST /api/procurements/{id}/cast_vote/ - cast a supplier vote
    - GET /api/procurements/{id}/vote_results/ - get vote results
    - POST /api/procurements/{id}/approve_supplier/ - organizer approves supplier
    - POST /api/procurements/{id}/stop_amount/ - organizer triggers stop-amount
    - GET /api/procurements/{id}/receipt_table/ - generate receipt table for supplier
    - POST /api/procurements/{id}/close/ - organizer closes completed procurement
    """
    queryset = Procurement.objects.select_related('category', 'organizer')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'city']
    ordering_fields = ['created_at', 'deadline', 'target_amount', 'current_amount']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProcurementListSerializer
        if self.action == 'create':
            return ProcurementCreateSerializer
        return ProcurementDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)

        # Filter by city
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)

        # Filter by organizer
        organizer = self.request.query_params.get('organizer')
        if organizer:
            queryset = queryset.filter(organizer_id=organizer)

        # Filter active only
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(status=Procurement.Status.ACTIVE)

        return queryset

    def perform_create(self, serializer):
        """Create procurement with active status"""
        serializer.save(status=Procurement.Status.ACTIVE)

    @action(detail=True, methods=['get'])
    def participants(self, request, pk=None):
        """Get list of participants for a procurement"""
        procurement = self.get_object()
        participants = procurement.participants.filter(is_active=True)
        serializer = ParticipantSerializer(participants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join a procurement"""
        procurement = self.get_object()

        if not procurement.can_join:
            return Response(
                {'error': 'Cannot join this procurement'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = JoinProcurementSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = serializer.validated_data['user_id']

        # Check if already participating
        if procurement.participants.filter(user_id=user_id, is_active=True).exists():
            return Response(
                {'error': 'Already participating in this procurement'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create participant
        participant = Participant.objects.create(
            procurement=procurement,
            user_id=user_id,
            quantity=serializer.validated_data['quantity'],
            amount=serializer.validated_data['amount'],
            notes=serializer.validated_data.get('notes', ''),
            status=Participant.Status.PENDING
        )

        return Response(
            ParticipantSerializer(participant).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """Add another user to a procurement (organizer only).

        The organizer can invite/add another user by specifying user_id,
        quantity, and amount.  The new participant starts in PENDING status.
        """
        procurement = self.get_object()

        serializer = AddParticipantSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        organizer_id = serializer.validated_data['organizer_id']
        user_id = serializer.validated_data['user_id']

        if procurement.organizer_id != int(organizer_id):
            return Response(
                {'error': 'Only the organizer can add participants to this procurement'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not procurement.can_join:
            return Response(
                {'error': 'Cannot add participants to this procurement'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if procurement.participants.filter(user_id=user_id, is_active=True).exists():
            return Response(
                {'error': 'User is already participating in this procurement'},
                status=status.HTTP_400_BAD_REQUEST
            )

        participant = Participant.objects.create(
            procurement=procurement,
            user_id=user_id,
            quantity=serializer.validated_data['quantity'],
            amount=serializer.validated_data['amount'],
            notes=serializer.validated_data.get('notes', ''),
            status=Participant.Status.PENDING,
        )

        return Response(
            ParticipantSerializer(participant).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave a procurement"""
        procurement = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        participant = procurement.participants.filter(user_id=user_id, is_active=True).first()
        if not participant:
            return Response(
                {'error': 'Not participating in this procurement'},
                status=status.HTTP_400_BAD_REQUEST
            )

        participant.is_active = False
        participant.status = Participant.Status.CANCELLED
        participant.save()

        return Response({'message': 'Successfully left the procurement'})

    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    def user_procurements(self, request, user_id=None):
        """Get procurements for a specific user"""
        # Validate that user_id is an integer (Django User pk).
        # A UUID or any non-integer value would cause a ValueError in the ORM.
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return Response({'organized': [], 'participating': []})

        # Get organized procurements
        organized = self.get_queryset().filter(organizer_id=user_id)

        # Fetch all user participants in a single query to avoid N+1
        user_participants = {
            p.procurement_id: p
            for p in Participant.objects.filter(user_id=user_id, is_active=True)
        }
        participating = self.get_queryset().filter(id__in=user_participants.keys())

        organized_data = ProcurementListSerializer(organized, many=True).data
        participating_data = ProcurementListSerializer(participating, many=True).data

        # Add user's amount for participating procurements (no extra DB queries)
        for proc_data in participating_data:
            participant = user_participants.get(proc_data['id'])
            if participant:
                proc_data['my_amount'] = str(participant.amount)
                proc_data['my_quantity'] = str(participant.quantity)

        return Response({
            'organized': organized_data,
            'participating': participating_data
        })

    @action(detail=True, methods=['post'])
    def check_access(self, request, pk=None):
        """Check if user has access to procurement chat"""
        procurement = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # User has access if they are organizer or participant
        has_access = (
            procurement.organizer_id == int(user_id) or
            procurement.participants.filter(user_id=user_id, is_active=True).exists()
        )

        if has_access:
            return Response({'access': True})
        return Response(
            {'access': False, 'error': 'No access to this procurement'},
            status=status.HTTP_403_FORBIDDEN
        )

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update procurement status - only the organizer can change status"""
        procurement = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if procurement.organizer_id != int(user_id):
            return Response(
                {'error': 'Only the organizer can change procurement status'},
                status=status.HTTP_403_FORBIDDEN
            )

        new_status = request.data.get('status')

        if new_status not in dict(Procurement.Status.choices):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        procurement.status = new_status
        procurement.save(update_fields=['status', 'updated_at'])

        return Response({
            'status': procurement.status,
            'status_display': procurement.status_display
        })

    # ------------------------------------------------------------------
    # Supplier voting (docs section 2.3, 2.4, 10.1-10.2)
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def cast_vote(self, request, pk=None):
        """Cast a vote for a supplier.

        A participant casts exactly one vote per procurement (unique constraint).
        The procurement must be in ACTIVE or STOPPED status to allow voting.
        """
        procurement = self.get_object()

        if procurement.status not in (Procurement.Status.ACTIVE, Procurement.Status.STOPPED):
            return Response(
                {'error': 'Voting is only allowed while the procurement is active or stopped'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CastVoteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        voter_id = serializer.validated_data['voter_id']
        supplier_id = serializer.validated_data['supplier_id']
        comment = serializer.validated_data.get('comment', '')

        # Voter must be a participant or the organizer
        is_participant = procurement.participants.filter(user_id=voter_id, is_active=True).exists()
        is_organizer = procurement.organizer_id == voter_id
        if not is_participant and not is_organizer:
            return Response(
                {'error': 'Only participants or the organizer can vote'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Upsert: update existing vote or create new one
        vote, created = SupplierVote.objects.update_or_create(
            procurement=procurement,
            voter_id=voter_id,
            defaults={'supplier_id': supplier_id, 'comment': comment},
        )

        return Response(
            SupplierVoteSerializer(vote).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'])
    def vote_results(self, request, pk=None):
        """Get aggregated supplier vote results for a procurement."""
        procurement = self.get_object()

        results = (
            SupplierVote.objects.filter(procurement=procurement)
            .values('supplier', 'supplier__first_name', 'supplier__last_name')
            .annotate(vote_count=Count('id'))
            .order_by('-vote_count')
        )

        total_votes = sum(r['vote_count'] for r in results)

        data = []
        for r in results:
            supplier_name = f"{r['supplier__first_name']} {r['supplier__last_name']}".strip()
            data.append({
                'supplier_id': r['supplier'],
                'supplier_name': supplier_name,
                'vote_count': r['vote_count'],
                'percentage': round(r['vote_count'] / total_votes * 100, 1) if total_votes else 0,
            })

        return Response({
            'procurement_id': procurement.id,
            'total_votes': total_votes,
            'results': data,
        })

    @action(detail=True, methods=['post'])
    def close_vote(self, request, pk=None):
        """Record that a participant wants to close the supplier vote.

        Each active participant or organizer can submit this once.  Returns
        how many have confirmed so far and the total number of participants.
        """
        procurement = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Must be a participant or organizer
        is_participant = procurement.participants.filter(user_id=user_id, is_active=True).exists()
        is_organizer = procurement.organizer_id == int(user_id)
        if not is_participant and not is_organizer:
            return Response(
                {'error': 'Only participants or the organizer can close the vote'},
                status=status.HTTP_403_FORBIDDEN
            )

        VoteCloseRequest.objects.get_or_create(
            procurement=procurement,
            user_id=user_id,
        )

        closed_by = list(
            VoteCloseRequest.objects.filter(procurement=procurement)
            .values_list('user_id', flat=True)
        )
        total_participants = procurement.participants.filter(is_active=True).count()

        return Response({
            'procurement_id': procurement.id,
            'closed_by': closed_by,
            'close_count': len(closed_by),
            'total_participants': total_participants,
        })

    @action(detail=True, methods=['get'])
    def vote_close_status(self, request, pk=None):
        """Get the current vote-close confirmation status for a procurement."""
        procurement = self.get_object()

        closed_by = list(
            VoteCloseRequest.objects.filter(procurement=procurement)
            .values_list('user_id', flat=True)
        )
        total_participants = procurement.participants.filter(is_active=True).count()

        return Response({
            'procurement_id': procurement.id,
            'closed_by': closed_by,
            'close_count': len(closed_by),
            'total_participants': total_participants,
        })

    # ------------------------------------------------------------------
    # Organizer actions (docs section 2.2 – slider buttons)
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def approve_supplier(self, request, pk=None):
        """Organizer approves (confirms) the winning supplier.

        Sets procurement.supplier to the given supplier_id and transitions
        the procurement status to PAYMENT so participants can confirm and pay.
        """
        procurement = self.get_object()
        supplier_id = request.data.get('supplier_id')

        if not supplier_id:
            return Response(
                {'error': 'supplier_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        procurement.supplier_id = supplier_id
        procurement.status = Procurement.Status.PAYMENT
        procurement.save(update_fields=['supplier_id', 'status', 'updated_at'])

        return Response({
            'message': 'Supplier approved',
            'supplier_id': supplier_id,
            'status': procurement.status,
        })

    @action(detail=True, methods=['post'])
    def stop_amount(self, request, pk=None):
        """Organizer triggers stop-amount: closes procurement to new participants.

        Transitions procurement to STOPPED status and notifies confirmed
        participants that they should confirm their final participation.
        Any participant that is PENDING is asked to confirm; this endpoint
        returns the list of confirmed participants so the caller can create
        the closed chat.
        """
        procurement = self.get_object()

        if procurement.status != Procurement.Status.ACTIVE:
            return Response(
                {'error': 'Only active procurements can be stopped'},
                status=status.HTTP_400_BAD_REQUEST
            )

        procurement.status = Procurement.Status.STOPPED
        procurement.save(update_fields=['status', 'updated_at'])

        confirmed_participants = procurement.participants.filter(is_active=True)
        serializer = ParticipantSerializer(confirmed_participants, many=True)

        return Response({
            'message': 'Procurement stopped – participants should confirm participation',
            'status': procurement.status,
            'participants': serializer.data,
        })

    @action(detail=True, methods=['get'])
    def receipt_table(self, request, pk=None):
        """Generate receipt table for the supplier.

        Returns a list of confirmed/paid participants with their order details
        so the organizer can send the summary spreadsheet to the supplier.
        """
        procurement = self.get_object()

        participants = procurement.participants.filter(
            is_active=True,
            status__in=[Participant.Status.CONFIRMED, Participant.Status.PAID],
        ).select_related('user')

        rows = []
        total_amount = 0
        for p in participants:
            rows.append({
                'user_id': p.user_id,
                'full_name': p.user.full_name,
                'phone': p.user.phone,
                'city': procurement.city,
                'quantity': str(p.quantity),
                'amount': str(p.amount),
                'status': p.status,
                'notes': p.notes,
            })
            total_amount += float(p.amount)

        commission = float(procurement.commission_percent) / 100 * total_amount

        return Response({
            'procurement_id': procurement.id,
            'procurement_title': procurement.title,
            'supplier_id': procurement.supplier_id,
            'unit': procurement.unit,
            'total_participants': len(rows),
            'total_amount': round(total_amount, 2),
            'commission_percent': str(procurement.commission_percent),
            'commission_amount': round(commission, 2),
            'rows': rows,
        })

    @action(detail=True, methods=['post'])
    def send_to_supplier(self, request, pk=None):
        """Enqueue a document export job to send procurement data to the supplier.

        Idempotency: provide `idempotency_key` in the request body to avoid duplicate sends.
        If omitted, a unique key is generated automatically.

        Status flow: pending → processing → sent | failed_retry | fatal_error
        Full request/response payloads are logged to supplier_document_jobs for audit.

        The actual HTTP call to the supplier API happens here synchronously (for simplicity).
        In a high-load production system, move the HTTP call to a Celery/BullMQ worker that
        reads from pending/failed_retry jobs.
        """
        import requests as http_requests  # lazy import to avoid top-level side-effects

        procurement = self.get_object()

        organizer_id = request.data.get('organizer_id')
        supplier_api_url = request.data.get('supplier_api_url', '')
        idempotency_key = request.data.get('idempotency_key') or str(uuid_lib.uuid4())
        job_type = request.data.get('job_type', 'receipt_table')

        if not organizer_id or procurement.organizer_id != int(organizer_id):
            return Response(
                {'status': 403, 'code': 'SEND_FORBIDDEN', 'message': 'Only the organizer can send documents'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Build the document payload (snapshot at time of job creation)
        participants = procurement.participants.filter(
            is_active=True,
            status__in=[Participant.Status.CONFIRMED, Participant.Status.PAID],
        ).select_related('user')

        rows = []
        total_amount = 0
        for p in participants:
            rows.append({
                'user_id': p.user_id,
                'full_name': p.user.full_name,
                'phone': p.user.phone,
                'city': procurement.city,
                'quantity': str(p.quantity),
                'amount': str(p.amount),
                'status': p.status,
                'notes': p.notes,
            })
            total_amount += float(p.amount)

        commission = float(procurement.commission_percent) / 100 * total_amount
        doc_payload = {
            'procurement_id': procurement.id,
            'procurement_title': procurement.title,
            'supplier_id': procurement.supplier_id,
            'unit': procurement.unit,
            'total_participants': len(rows),
            'total_amount': round(total_amount, 2),
            'commission_percent': str(procurement.commission_percent),
            'commission_amount': round(commission, 2),
            'rows': rows,
        }

        # Create or retrieve existing job (idempotency)
        with db_transaction.atomic():
            job, created = SupplierDocumentJob.objects.get_or_create(
                procurement=procurement,
                job_type=job_type,
                idempotency_key=idempotency_key,
                defaults={
                    'organizer_id': organizer_id,
                    'status': SupplierDocumentJob.Status.PENDING,
                    'supplier_api_url': supplier_api_url,
                    'request_payload': doc_payload,
                    'retry_count': 0,
                },
            )

        if not created and job.status == SupplierDocumentJob.Status.SENT:
            # Already delivered — return cached result (idempotent)
            return Response({'success': True, 'idempotent': True, 'job_id': job.id,
                             'status': job.status}, status=status.HTTP_200_OK)

        if job.retry_count >= job.max_retries:
            job.status = SupplierDocumentJob.Status.FATAL_ERROR
            job.save(update_fields=['status', 'updated_at'])
            return Response(
                {'status': 429, 'code': 'MAX_RETRIES_EXCEEDED',
                 'message': f'Job {job.id} has exceeded max retries'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Mark as processing
        job.status = SupplierDocumentJob.Status.PROCESSING
        job.last_attempt_at = timezone.now()
        job.save(update_fields=['status', 'last_attempt_at', 'updated_at'])

        # Attempt delivery to supplier API
        try:
            if supplier_api_url:
                resp = http_requests.post(
                    supplier_api_url,
                    json=doc_payload,
                    timeout=30,
                )
                resp_payload = {}
                try:
                    resp_payload = resp.json()
                except Exception:
                    resp_payload = {'raw': resp.text[:2000]}

                if resp.ok:
                    job.status = SupplierDocumentJob.Status.SENT
                    job.sent_at = timezone.now()
                    job.response_payload = resp_payload
                else:
                    job.retry_count += 1
                    if job.retry_count >= job.max_retries:
                        job.status = SupplierDocumentJob.Status.FATAL_ERROR
                    else:
                        job.status = SupplierDocumentJob.Status.FAILED_RETRY
                    job.response_payload = resp_payload
                    job.error_message = f'HTTP {resp.status_code}: {resp.text[:500]}'
            else:
                # No supplier API URL configured — mark as sent (local delivery / webhook)
                job.status = SupplierDocumentJob.Status.SENT
                job.sent_at = timezone.now()
                job.response_payload = {'note': 'No supplier_api_url provided; payload stored locally'}

        except Exception as exc:
            job.retry_count += 1
            if job.retry_count >= job.max_retries:
                job.status = SupplierDocumentJob.Status.FATAL_ERROR
            else:
                job.status = SupplierDocumentJob.Status.FAILED_RETRY
            job.error_message = str(exc)[:1000]
            logger.error(
                'send_to_supplier job %s failed (attempt %s/%s): %s',
                job.id, job.retry_count, job.max_retries, exc,
            )

        job.save(update_fields=['status', 'retry_count', 'response_payload',
                                'error_message', 'sent_at', 'updated_at'])

        response_status = status.HTTP_200_OK if job.status == SupplierDocumentJob.Status.SENT else status.HTTP_202_ACCEPTED
        return Response({
            'success': job.status == SupplierDocumentJob.Status.SENT,
            'job_id': job.id,
            'status': job.status,
            'retry_count': job.retry_count,
        }, status=response_status)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Organizer closes a completed procurement and moves it to history."""
        procurement = self.get_object()

        if procurement.status not in (
            Procurement.Status.PAYMENT,
            Procurement.Status.STOPPED,
        ):
            return Response(
                {'error': 'Only procurements in payment or stopped status can be closed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        procurement.status = Procurement.Status.COMPLETED
        procurement.save(update_fields=['status', 'updated_at'])

        return Response({
            'message': 'Procurement closed successfully',
            'status': procurement.status,
        })

    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        """Invite a user to a procurement by email (creator only).

        Only the procurement organizer (creator) can send invites.
        The invite is logged; an email notification would be sent in production.
        """
        procurement = self.get_object()

        serializer = InviteUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        organizer_id = serializer.validated_data.get('organizer_id')
        email = serializer.validated_data['email']

        if organizer_id is None or procurement.organizer_id != int(organizer_id):
            return Response(
                {'error': 'Only the creator of this procurement can send invitations'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Log the invite (send email in production via async task or notification service)
        logger.info(
            'Procurement invite: procurement_id=%s organizer_id=%s invited_email=%s',
            procurement.id,
            procurement.organizer_id,
            email,
        )

        return Response({
            'message': f'Invitation sent to {email}',
            'procurement_id': procurement.id,
            'invited_email': email,
        }, status=status.HTTP_200_OK)


class ParticipantViewSet(viewsets.ModelViewSet):
    """ViewSet for managing participants"""
    queryset = Participant.objects.select_related('user', 'procurement')
    serializer_class = ParticipantSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by procurement
        procurement = self.request.query_params.get('procurement')
        if procurement:
            queryset = queryset.filter(procurement_id=procurement)

        # Filter by user
        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user_id=user)

        return queryset

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update participant status"""
        participant = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(Participant.Status.choices):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        participant.status = new_status
        participant.save(update_fields=['status', 'updated_at'])

        return Response(ParticipantSerializer(participant).data)
