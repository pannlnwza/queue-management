from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.shortcuts import get_object_or_404
from django.utils import timezone
from manager.models import Queue
from manager.utils.category_handler import CategoryHandlerFactory
from django.utils.timezone import timedelta


class StatisticsView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'manager/statistics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queue_id = self.kwargs.get('queue_id')
        queue = get_object_or_404(Queue, id=queue_id)
        handler = CategoryHandlerFactory.get_handler(queue.category)
        queue = handler.get_queue_object(queue_id)
        participant_set = handler.get_participant_set(queue_id)

        date_filter = self.request.GET.get('date_filter', 'today')
        date_filter_text = 'today'
        end_date = timezone.now()

        if date_filter == 'today':
            start_date = end_date.replace(hour=0, minute=0, second=0,
                                          microsecond=0)
            date_filter_text = 'today'
        elif date_filter == 'last_7_days':
            start_date = end_date - timedelta(days=7)
            date_filter_text = 'last 7 days'
        elif date_filter == 'last_30_days':
            start_date = end_date - timedelta(days=30)
            date_filter_text = 'last 30 days'
        elif date_filter == 'all_time':
            start_date = None
            date_filter_text = 'all time'
        else:
            start_date = None

        context['queue'] = queue
        context['participant_set'] = participant_set
        context['waitlisted'] = queue.get_number_of_participants_by_date(
            start_date, end_date)
        context['currently_waiting'] = queue.get_number_waiting_now(start_date,
                                                                    end_date)
        context['currently_serving'] = queue.get_number_serving_now(start_date,
                                                                    end_date)
        context['served'] = queue.get_number_served(start_date, end_date)
        context['served_percentage'] = queue.get_served_percentage(start_date,
                                                                   end_date)
        context['average_wait_time'] = queue.get_average_waiting_time(
            start_date, end_date)
        context['max_wait_time'] = queue.get_max_waiting_time(start_date,
                                                              end_date)
        context[
            'average_service_duration'] = queue.get_average_service_duration(
            start_date, end_date)
        context['max_service_duration'] = queue.get_max_service_duration(
            start_date, end_date)
        context['peak_line_length'] = queue.get_peak_line_length(start_date,
                                                                 end_date)
        context['avg_line_length'] = queue.get_avg_line_length(start_date,
                                                               end_date)
        context['dropoff_percentage'] = queue.get_dropoff_percentage(
            start_date, end_date)
        context['unhandled_percentage'] = queue.get_unhandled_percentage(
            start_date, end_date)
        context['cancelled_percentage'] = queue.get_cancelled_percentage(
            start_date, end_date)
        context['no_show_percentage'] = queue.get_no_show_percentage(
            start_date, end_date)
        context['guest_percentage'] = queue.get_guest_percentage(start_date,
                                                                 end_date)
        context['staff_percentage'] = queue.get_staff_percentage(start_date,
                                                                 end_date)
        context['date_filter'] = date_filter
        context['date_filter_text'] = date_filter_text
        context['resource_totals'] = [
            {
                'resource': resource,
                'name': resource.name,
                'total': resource.total(start_date=start_date,
                                        end_date=end_date),
                'served': resource.served(start_date=start_date,
                                          end_date=end_date),
                'dropoff': resource.dropoff(start_date=start_date,
                                            end_date=end_date),
                'completed': resource.completed(start_date=start_date,
                                                end_date=end_date),
                'avg_wait_time': resource.avg_wait_time(start_date=start_date,
                                                        end_date=end_date),
                'avg_serve_time': resource.avg_serve_time(
                    start_date=start_date, end_date=end_date),
            }
            for resource in queue.resource_set.all()
        ]

        return context
