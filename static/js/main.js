import { createIcons, icons } from 'lucide';

document.addEventListener('DOMContentLoaded', () => {
  createIcons({ icons });
});


import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';

// DOM Loaded
document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');

    if (calendarEl) {
        const calendar = new Calendar(calendarEl, {
            plugins: [dayGridPlugin, interactionPlugin],
            initialView: 'dayGridMonth',
            selectable: true,
            events: '/calendar/events/',  
            dateClick(info) {
                alert('Create a reminder for ' + info.dateStr);
            },
            eventClick(info) {
                alert('Clicked on: ' + info.event.title);
            }
        });

        calendar.render();
    }
});
