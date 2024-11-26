from abc import ABC, abstractmethod
from django.shortcuts import get_object_or_404
from django.utils import timezone
from manager.utils.helpers import extract_data_variables
from django.apps import apps


class CategoryHandlerFactory:
    _handlers = {}

    @staticmethod
    def get_handler(queue_category):
        if queue_category in CategoryHandlerFactory._handlers:
            return CategoryHandlerFactory._handlers[queue_category]

        if queue_category == 'general':
            handler = GeneralQueueHandler()
        elif queue_category == 'restaurant':
            handler = RestaurantQueueHandler()
        elif queue_category == 'bank':
            handler = BankQueueHandler()
        elif queue_category == 'hospital':
            handler = HospitalQueueHandler()
        else:
            handler = GeneralQueueHandler()

        CategoryHandlerFactory._handlers[queue_category] = handler
        return handler


class CategoryHandler(ABC):
    @abstractmethod
    def create_queue(self, data):
        pass

    @abstractmethod
    def create_participant(self, data):
        pass

    @abstractmethod
    def get_participant_set(self, queue_id):
        pass

    @abstractmethod
    def get_queue_object(self, queue_id):
        pass

    @abstractmethod
    def assign_to_resource(self, participant, resource_id=None):
        pass

    @abstractmethod
    def complete_service(self, participant):
        pass

    @abstractmethod
    def add_context_attributes(self, queue):
        """Returns restaurant-specific attributes for the context."""
        pass

    @abstractmethod
    def get_template_name(self):
        """Return the template name specific to the handler's category."""
        pass

    @abstractmethod
    def get_participant_data(self, participant):
        pass

    @abstractmethod
    def update_participant(self, participant, data):
        pass

    @abstractmethod
    def add_resource_attributes(self, queue):
        pass

    @abstractmethod
    def add_resource(self, queue):
        pass

    @abstractmethod
    def edit_resource(self, resource, data):
        pass


class GeneralQueueHandler(CategoryHandler):
    def create_queue(self, data):
        Queue = apps.get_model('manager', 'Queue')  # Lazy load
        User = apps.get_model('auth', 'User')  # Lazy load
        user_id = data.pop("created_by_id", None)
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                data["created_by"] = user
            except User.DoesNotExist:
                raise ValueError(f"User with id {user_id} does not exist.")
        return Queue.objects.create(**data)

    def create_participant(self, data):
        Participant = apps.get_model('participant', 'Participant')  # Lazy load
        participant_info = extract_data_variables(data)
        queue_length = participant_info['queue'].participant_set.filter(state='waiting').count()
        return Participant.objects.create(
            name=participant_info['name'],
            email=participant_info['email'],
            phone=participant_info['phone'],
            note=participant_info['note'],
            queue=participant_info['queue'],
            position=queue_length + 1
        )

    def get_participant_set(self, queue_id):
        Participant = apps.get_model('participant', 'Participant')  # Lazy load
        return Participant.objects.filter(queue_id=queue_id)

    def get_queue_object(self, queue_id):
        Queue = apps.get_model('manager', 'Queue')  # Lazy load
        return get_object_or_404(Queue, id=queue_id)

    def assign_to_resource(self, participant, resource_id=None):
        pass

    def complete_service(self, participant):
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_time = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_time
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
            participant.save()

    def get_template_name(self):
        return 'manager/manage_queue/manage_general.html'

    def add_context_attributes(self, queue):
        pass

    def update_participant(self, participant, data):
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.note = data.get('notes') or ""
        participant.state = data.get('state', participant.state)
        participant.save()

    def get_participant_data(self, participant):
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'email': participant.email,
            'position': participant.position,
            'notes': participant.note,
            'waited': participant.get_wait_time(),
            'is_notified': participant.is_notified,
            'estimated_wait_time': participant.calculate_estimated_wait_time()

        }

    def get_special_column(self):
        pass

    def add_resource_attributes(self, queue, resource_id=None):
        pass

    def add_resource(self, queue):
        pass

    def edit_resource(self, resource, data):
        pass


class RestaurantQueueHandler(CategoryHandler):
    def create_queue(self, data):
        RestaurantQueue = apps.get_model('manager', 'RestaurantQueue')  # Lazy load
        User = apps.get_model('auth', 'User')  # Lazy load
        user_id = data.pop("created_by_id", None)
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                data["created_by"] = user
            except User.DoesNotExist:
                raise ValueError(f"User with id {user_id} does not exist.")
        return RestaurantQueue.objects.create(**data)

    def create_participant(self, data):
        RestaurantParticipant = apps.get_model('participant', 'RestaurantParticipant')  # Lazy load
        participant_info = extract_data_variables(data)
        queue_length = participant_info['queue'].participant_set.filter(state='waiting').count()
        return RestaurantParticipant.objects.create(
            name=participant_info['name'],
            email=participant_info['email'],
            phone=participant_info['phone'],
            note=participant_info['note'],
            queue=participant_info['queue'],
            party_size=participant_info['special_1'],
            service_type=participant_info['special_2'],
            position=queue_length + 1,
            created_by='staff'
        )

    def assign_to_resource(self, participant, resource_id=None):
        Table = apps.get_model('manager', 'Table')  # Lazy load
        queue = participant.queue
        if resource_id:
            resource = get_object_or_404(Table, id=resource_id)
        else:
            resource = queue.get_available_resource(required_capacity=participant.party_size)
        if not resource:
            raise ValueError('No resource available.')
        resource.assign_to_participant(participant, capacity=participant.party_size)
        participant.resource = resource
        participant.resource_assigned = resource.name
        participant.save()

    def get_participant_set(self, queue_id):
        RestaurantParticipant = apps.get_model('participant', 'RestaurantParticipant')
        return RestaurantParticipant.objects.filter(queue_id=queue_id).all()

    def get_queue_object(self, queue_id):
        RestaurantQueue = apps.get_model('manager', 'RestaurantQueue')
        return get_object_or_404(RestaurantQueue, id=queue_id)

    def get_template_name(self):
        return 'manager/manage_queue/manage_unique_category.html'

    def complete_service(self, participant):
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_duration = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_duration
            service_duration = int((timezone.localtime() - participant.service_started_at).total_seconds() / 60)
            participant.service_duration = service_duration
            if participant.resource:
                participant.resource_assigned = participant.resource.name
                participant.resource.free()
                participant.resource = None
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()

        else:
            participant.state = 'completed'
        participant.save()

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        RestaurantParticipant = apps.get_model('participant', 'RestaurantParticipant')
        return {
            'special_1': 'Party Size',
            'special_2': 'Service Type',
            'resource_name': 'Table',
            'special_1_choices': None,
            'special_2_choices': RestaurantParticipant.SERVICE_TYPE_CHOICE
        }

    def update_participant(self, participant, data):
        Table = apps.get_model('participant', 'Table')
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.party_size = data.get('special_1', participant.party_size)
        participant.service_type = data.get('special_2', participant.service_type)
        participant.note = data.get('notes') or ""
        new_state = data.get('state')
        participant.email = data.get('email', participant.email)
        participant.save()

        if new_state == 'completed':
            self.complete_service(participant)
        else:
            table_id = data.get('resource')
            if table_id:
                table = get_object_or_404(Table, id=table_id)
                table.assign_to_participant(participant=participant)
                participant.resource = table
                participant.service_started_at = timezone.localtime()
                participant.save()

            else:
                if participant.resource:
                    participant.resource.free()
                    participant.resource = None
                    participant.state = 'waiting'
                    participant.service_started_at = None
                participant.save()
            participant.state = new_state
            participant.save()

    def get_participant_data(self, participant):
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'email': participant.email,
            'position': participant.position,
            'notes': participant.note,
            'waited': participant.waited if participant.state == 'completed' else participant.get_wait_time(),
            'completed': timezone.localtime(participant.service_completed_at).strftime('%d %b. %Y %H:%M') if participant.service_completed_at else None,
            'special_1': f"{participant.party_size} people",
            'special_2': participant.get_service_type_display(),
            'service_duration': participant.get_service_duration(),
            'served': timezone.localtime(participant.service_started_at).strftime('%d %b. %Y %H:%M') if participant.service_started_at else None,
            'resource_served': participant.resource_assigned,
            'resource': participant.resource.name if participant.resource else None,
            'resource_id': participant.resource.id if participant.resource else None,
            'is_notified': participant.is_notified,
            'estimated_wait_time': participant.calculate_estimated_wait_time()
        }

    def add_resource_attributes(self, queue):
        return {
            'resource_name': 'Table',
            'special_column': 'Capacity',
        }

    def add_resource(self, data):
        Table = apps.get_model('participant', 'Table')
        name = data.get('name')
        capacity = data.get('special')
        status = data.get('status')
        queue = data.get('queue')
        table = Table.objects.create(name=name, capacity=capacity, status=status, queue=queue)
        queue.resources.add(table)
        queue.save()

    def edit_resource(self, resource, data):
        RestaurantParticipant = apps.get_model('participant', 'RestaurantParticipant')
        resource.name = data.get('name', resource.name)
        resource.capacity = data.get('special', resource.capacity)
        resource.status = data.get('status', resource.status)
        assigned_to = data.get('assigned_to', resource.assigned_to)

        try:
            participant = get_object_or_404(RestaurantParticipant, id=assigned_to) if assigned_to else None
            if participant:
                if not resource.assigned_to or int(assigned_to) != int(resource.assigned_to.id):
                    resource.free()
                    self.assign_to_resource(participant, resource)
            elif not assigned_to and resource.assigned_to:
                resource.free()
            elif not assigned_to and not resource.assigned_to:
                pass

        except RestaurantParticipant.DoesNotExist:
            print(f"Participant with ID {assigned_to} does not exist.")
        resource.save()

    def get_participant_type(self):
        """Return Restaurant Participanti subclass"""
        RestaurantParticipant = apps.get_model('participant', 'RestaurantParticipant')
        return RestaurantParticipant


class HospitalQueueHandler(CategoryHandler):
    def create_queue(self, data):
        HospitalQueue = apps.get_model('manager', 'HospitalQueue')  # Lazy load
        User = apps.get_model('auth', 'User')  # Lazy load
        user_id = data.pop("created_by_id", None)
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                data["created_by"] = user
            except User.DoesNotExist:
                raise ValueError(f"User with id {user_id} does not exist.")
        return HospitalQueue.objects.create(**data)

    def create_participant(self, data):
        HospitalParticipant = apps.get_model('participant', 'HospitalParticipant')  # Lazy load
        participant_info = extract_data_variables(data)
        queue_length = participant_info['queue'].participant_set.filter(state='waiting').count()
        return HospitalParticipant.objects.create(
            name=participant_info['name'],
            email=participant_info['email'],
            phone=participant_info['phone'],
            note=participant_info['note'],
            queue=participant_info['queue'],
            medical_field=participant_info['special_1'],
            priority=participant_info['special_2'],
            position=queue_length + 1,
            created_by='staff'
        )

    def get_participant_set(self, queue_id):
        """
        Returns all participants in a hospital queue.
        """
        HospitalParticipant = apps.get_model('participant', 'HospitalParticipant')  # Lazy load
        return HospitalParticipant.objects.filter(queue_id=queue_id).all()

    def get_queue_object(self, queue_id):
        """
        Fetches the hospital queue by ID.
        """
        HospitalQueue = apps.get_model('manager', 'HospitalQueue')  # Lazy load
        return get_object_or_404(HospitalQueue, id=queue_id)

    def assign_to_resource(self, participant, resource_id=None):
        """
        Assigns a doctor to a hospital participant based on their medical field and priority.
        """
        Doctor = apps.get_model('manager', 'Doctor')  # Lazy load
        if resource_id:
            resource = get_object_or_404(Doctor, id=resource_id)
        else:
            resource = Doctor.objects.filter(specialty=participant.medical_field, status='available').first()
        if not resource:
            raise ValueError('No resource available.')
        resource.assign_to_participant(participant)
        participant.resource = resource
        participant.resource_assigned = resource.name
        participant.save()

    def get_template_name(self):
        """
        Returns the template name for the hospital queue management.
        """
        return 'manager/manage_queue/manage_hospital.html'

    def complete_service(self, participant):
        """
        Completes the service for the hospital participant.
        """
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_duration = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_duration
            service_duration = int((timezone.localtime() - participant.service_started_at).total_seconds() / 60)
            participant.service_duration = service_duration
            if participant.resource:
                participant.resource_assigned = participant.resource.name
                participant.resource.free()
                participant.resource = None
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
        else:
            participant.state = 'completed'
        participant.save()

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        Doctor = apps.get_model('manager', 'Doctor')  # Lazy load
        HospitalParticipant = apps.get_model('participant', 'HospitalParticipant')
        return {
            'special_1': 'Medical Field Needed',
            'special_2': 'Priority',
            'resource_name': 'Doctor',
            'resources': Doctor.objects.filter(queue=queue),
            'special_1_choices': HospitalParticipant.MEDICAL_FIELD_CHOICES,
            'special_2_choices': HospitalParticipant.PRIORITY_CHOICES
        }

    def update_participant(self, participant, data):
        """
        Updates participant data like priority, medical field, etc.
        """
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.medical_field = data.get('special_1', participant.medical_field)
        participant.priority = data.get('special_2', participant.priority)
        participant.note = data.get('notes') or ""
        participant.email = data.get('email', participant.email)

        # Determine if the state should be updated
        new_state = data.get('state', participant.state)
        participant.state = new_state
        participant.save()

        # Check if service is marked as completed
        if new_state == 'completed':
            self.complete_service(participant)
        else:
            # Handle resource assignment (e.g., doctor)
            doctor_id = data.get('resource')
            if doctor_id:
                Doctor = apps.get_model('manager', 'Doctor')  # Lazy load
                doctor = get_object_or_404(Doctor, id=doctor_id)
                doctor.assign_to_participant(participant=participant)
                participant.resource = doctor
                participant.service_started_at = timezone.localtime()
                participant.save()

            else:
                if participant.resource:
                    participant.resource.free()
                    participant.resource = None
                    participant.state = 'waiting'
                    participant.service_started_at = None
                participant.save()
            participant.state = new_state
            participant.save()

    def get_participant_data(self, participant):
        """
        Returns participant data, including medical field and priority.
        """
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'email': participant.email,
            'position': participant.position,
            'notes': participant.note,
            'medical_field': participant.get_medical_field_display(),
            'priority': participant.get_priority_display(),
            'waited': participant.waited if participant.state == 'completed' else participant.get_wait_time(),
            'completed': timezone.localtime(participant.service_completed_at).strftime('%d %b. %Y %H:%M') if participant.service_completed_at else None,
            'special_1': participant.get_medical_field_display(),
            'special_2': participant.get_priority_display(),
            'service_duration': participant.get_service_duration(),
            'served': timezone.localtime(participant.service_started_at).strftime('%d %b. %Y %H:%M') if participant.service_started_at else None,
            'resource_served': participant.resource_assigned,
            'resource': participant.resource.name if participant.resource else None,
            'resource_id': participant.resource.id if participant.resource else None,
            'is_notified': participant.is_notified,
            'estimated_wait_time': participant.calculate_estimated_wait_time()
        }

    def add_resource_attributes(self, queue):
        Doctor = apps.get_model('manager', 'Doctor')  # Lazy load
        return {
            'resource_name': 'Doctor',
            'resources': Doctor.objects.filter(queue=queue),
            'special_column': 'Specialty',
            'special_choice': Doctor.MEDICAL_SPECIALTY_CHOICES,
        }

    def add_resource(self, data):
        Doctor = apps.get_model('manager', 'Doctor')  # Lazy load
        name = data.get('name')
        medical_field = data.get('special')
        status = data.get('status')
        queue = data.get('queue')
        doctor = Doctor.objects.create(name=name, specialty=medical_field, status=status, queue=queue)
        queue.resources.add(doctor)
        queue.save()

    def edit_resource(self, resource, data):
        Doctor = apps.get_model('manager', 'Doctor')  # Lazy load
        HospitalParticipant = apps.get_model('participant', 'HospitalParticipant')
        doctor = get_object_or_404(Doctor, id=resource.id)
        doctor.name = data.get('name', doctor.name)
        doctor.specialty = data.get('special', doctor.specialty)
        doctor.status = data.get('status', doctor.status)
        assigned_to = data.get('assigned_to', doctor.assigned_to)

        try:
            participant = get_object_or_404(HospitalParticipant, id=assigned_to) if assigned_to else None
            if participant:
                if not resource.assigned_to or int(assigned_to) != int(resource.assigned_to.id):
                    resource.free()
                    self.assign_to_resource(participant, resource)
            elif not assigned_to and resource.assigned_to:
                resource.free()
            elif not assigned_to and not resource.assigned_to:
                pass

        except HospitalParticipant.DoesNotExist:
            print(f"Participant with ID {assigned_to} does not exist.")
        resource.save()


class BankQueueHandler(CategoryHandler):
    def create_queue(self, data):
        BankQueue = apps.get_model('manager', 'BankQueue')  # Lazy load
        User = apps.get_model('auth', 'User')  # Lazy load
        user_id = data.pop("created_by_id", None)
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                data["created_by"] = user
            except User.DoesNotExist:
                raise ValueError(f"User with id {user_id} does not exist.")
        return BankQueue.objects.create(**data)

    def create_participant(self, data):
        BankParticipant = apps.get_model('participant', 'BankParticipant')  # Lazy load
        participant_info = extract_data_variables(data)
        queue_length = participant_info['queue'].participant_set.count()
        return BankParticipant.objects.create(
            name=participant_info['name'],
            email=participant_info['email'],
            phone=participant_info['phone'],
            note=participant_info['note'],
            queue=participant_info['queue'],
            participant_category=participant_info['special_1'],
            service_type=participant_info['special_2'],
            position=queue_length + 1,
            created_by='staff'
        )

    def get_participant_set(self, queue_id):
        BankParticipant = apps.get_model('participant', 'BankParticipant')
        return BankParticipant.objects.filter(queue_id=queue_id)

    def get_queue_object(self, queue_id):
        BankQueue = apps.get_model('manager', 'BankQueue')
        return get_object_or_404(BankQueue, id=queue_id)

    def assign_to_resource(self, participant, resource_id=None):
        Counter = apps.get_model('manager', 'Counter')
        if resource_id:
            resource = get_object_or_404(Counter, id=resource_id)
        else:
            resource = Counter.objects.filter(status='available').first()

        if not resource:
            raise ValueError('No resource available.')
        resource.assign_to_participant(participant)
        participant.resource = resource
        participant.resource_assigned = resource.name
        participant.save()

    def complete_service(self, participant):
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_duration = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_duration
            service_duration = int((timezone.localtime() - participant.service_started_at).total_seconds() / 60)
            participant.service_duration = service_duration
            if participant.resource:
                participant.resource_assigned = participant.resource.name
                participant.resource.free()
                participant.resource = None
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
        else:
            participant.state = 'completed'
        participant.save()

    def get_template_name(self):
        return 'manager/manage_queue/manage_bank.html'

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        BankParticipant = apps.get_model('participant', 'BankParticipant')
        return {
            'special_1': 'Customer Category',
            'special_2': 'Service Type',
            'resource_name': 'Counter',
            'special_1_choices': BankParticipant.PARTICIPANT_CATEGORY_CHOICES,
            'special_2_choices': BankParticipant.SERVICE_TYPE_CHOICES
        }

    def update_participant(self, participant, data):
        Counter = apps.get_model('manager', 'Counter')
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.participant_category = data.get('special_1', participant.participant_category)
        participant.service_type = data.get('special_2', participant.service_type)
        participant.note = data.get('notes') or ""
        new_state = data.get('state')
        participant.email = data.get('email', participant.email)
        participant.save()

        if new_state == 'completed':
            self.complete_service(participant)
        else:
            counter_id = data.get('resource')
            if counter_id:
                counter = get_object_or_404(Counter, id=counter_id)
                counter.assign_to_participant(participant=participant)
                participant.resource = counter
                participant.service_started_at = timezone.localtime()
                participant.save()

            else:
                if participant.resource:
                    participant.resource.free()
                    participant.resource = None
                    participant.state = 'waiting'
                    participant.service_started_at = None
                participant.save()
            participant.state = new_state
            participant.save()

    def get_participant_data(self, participant):
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'email': participant.email,
            'position': participant.position,
            'special_1': participant.get_participant_category_display(),
            'special_2': participant.get_service_type_display(),
            'notes': participant.note,
            'waited': participant.waited if participant.state == 'completed' else participant.get_wait_time(),
            'completed': timezone.localtime(participant.service_completed_at).strftime('%d %b. %Y %H:%M') if participant.service_completed_at else None,
            'service_duration': participant.get_service_duration(),
            'served': timezone.localtime(participant.service_started_at).strftime('%d %b. %Y %H:%M') if participant.service_started_at else None,
            'resource': participant.resource.name if participant.resource else None,
            'resource_id': participant.resource.id if participant.resource else None,
            'resource_served': participant.resource_assigned,
            'is_notified': participant.is_notified,
            'estimated_wait_time': participant.calculate_estimated_wait_time()
        }

    def add_resource_attributes(self, queue):
        Counter = apps.get_model('manager', 'Counter')
        return {
            'resource_name': 'Counter',
            'resources': Counter.objects.filter(queue=queue),
            'special_column': 'Service',
            'special_choice': Counter.SERVICE_TYPE_CHOICES,
        }

    def add_resource(self, data):
        Counter = apps.get_model('manager', 'Counter')
        name = data.get('name')
        service_type = data.get('special')
        status = data.get('status')
        queue = data.get('queue')
        counter = Counter.objects.create(name=name, service_type=service_type, status=status, queue=queue)
        queue.resources.add(counter)
        queue.save()

    def edit_resource(self, resource, data):
        Counter = apps.get_model('manager', 'Counter')
        BankParticipant = apps.get_model('participant', 'BankParticipant')
        counter = get_object_or_404(Counter, id=resource.id)
        counter.name = data.get('name', counter.name)
        counter.service_type = data.get('special', counter.service_type)
        counter.status = data.get('status', counter.status)
        assigned_to = data.get('assigned_to', counter.assigned_to)

        try:
            participant = get_object_or_404(BankParticipant, id=assigned_to) if assigned_to else None
            if participant:
                if not resource.assigned_to or int(assigned_to) != int(resource.assigned_to.id):
                    resource.free()
                    self.assign_to_resource(participant, resource)
            elif not assigned_to and resource.assigned_to:
                resource.free()
            elif not assigned_to and not resource.assigned_to:
                pass

        except BankParticipant.DoesNotExist:
            print(f"Participant with ID {assigned_to} does not exist.")
        resource.save()