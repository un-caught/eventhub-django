from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Event, Category, TicketType, Booking, Review, EventImage, Ticket
from .forms import EventForm, EventImageForm, TicketTypeForm, ReviewForm, ContactForm
from django.db.models import Count
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from django.http import HttpResponse, Http404
from io import BytesIO
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings
# Create your views here.

def home(request):
    categories = Category.objects.annotate(
        event_count=Count('event')
    ).order_by('-event_count')[:6]
    upcoming_events = Event.objects.filter(is_published=True).order_by('start_date')[:4]
    context = {
        'categories': categories,
        'upcoming_events': upcoming_events
    }
    return render(request, 'events/home.html', context)

def event_list(request):
    events = Event.objects.filter(is_published=True).order_by('start_date')
    
    # Filtering
    category = request.GET.get('category')
    if category:
        events = events.filter(category__name=category)
    
    event_type = request.GET.get('event_type')
    if event_type:
        events = events.filter(event_type=event_type)
    
    # Pagination
    paginator = Paginator(events, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
    }
    return render(request, 'events/event_list.html', context)

# def event_detail(request, pk):
#     event = get_object_or_404(Event, pk=pk)
#     ticket_types = event.ticket_types.all()
#     reviews = event.reviews.all()
    
#     if request.method == 'POST':
#         if 'review_submit' in request.POST:
#             review_form = ReviewForm(request.POST)
#             if review_form.is_valid():
#                 review = review_form.save(commit=False)
#                 review.event = event
#                 review.user = request.user
#                 review.save()
#                 messages.success(request, 'Your review has been posted!')
#                 return redirect('event-detail', pk=event.pk)
#         elif 'booking_submit' in request.POST:
#             ticket_type_id = request.POST.get('ticket_type')
#             quantity = int(request.POST.get('quantity', 1))
            
#             ticket_type = get_object_or_404(TicketType, pk=ticket_type_id)
            
#             if quantity > ticket_type.quantity:
#                 messages.error(request, 'Not enough tickets available!')
#             else:
#                 Booking.objects.create(
#                     user=request.user,
#                     ticket_type=ticket_type,
#                     quantity=quantity,
#                     is_paid=True  # Integrate with payment gateway when needed
#                 )
#                 ticket_type.quantity -= quantity
#                 ticket_type.save()
#                 messages.success(request, 'Your booking was successful!')
#                 return redirect('event-detail', pk=event.pk)
#     else:
#         review_form = ReviewForm()
    
#     context = {
#         'event': event,
#         'ticket_types': ticket_types,
#         'reviews': reviews,
#         'review_form': review_form,
#     }
#     return render(request, 'events/event_detail.html', context)


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    is_organizer = request.user == event.organizer

    ticket_form = TicketTypeForm()
    image_form = EventImageForm()
    review_form = ReviewForm()
    booking_submit = None
    
    # Handle form submissions
    if request.method == 'POST':
        if 'ticket_form' in request.POST:
            ticket_form = TicketTypeForm(request.POST)
            if ticket_form.is_valid():
                ticket = ticket_form.save(commit=False)
                ticket.event = event
                ticket.save()
                messages.success(request, 'Ticket type added successfully!')
                return redirect('event-detail', pk=event.pk)
        
        elif 'image_form' in request.POST:
            image_form = EventImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                image = image_form.save(commit=False)
                image.event = event
                image.save()
                messages.success(request, 'Image added successfully!')
                return redirect('event-detail', pk=event.pk)
        elif 'booking_submit' in request.POST:
            ticket_type_id = request.POST.get('ticket_type')
            quantity = int(request.POST.get('quantity', 1))
            
            try:
                ticket_type = TicketType.objects.get(pk=ticket_type_id, event=event)
                
                if quantity > ticket_type.quantity:
                    messages.error(request, 'Not enough tickets available!')
                else:
                    Booking.objects.create(
                        user=request.user,
                        ticket_type=ticket_type,
                        quantity=quantity,
                        is_paid=True  # Set to True if immediate payment
                    )
                    ticket_type.quantity -= quantity
                    ticket_type.save()
                    messages.success(request, 'Booking successful!')
                    return redirect('event-detail', pk=event.pk)
            except TicketType.DoesNotExist:
                messages.error(request, 'Invalid ticket selection')
        
        elif 'publish_toggle' in request.POST and is_organizer:
            event.is_published = not event.is_published
            event.save()
            status = "published" if event.is_published else "unpublished"
            messages.success(request, f'Event {status} successfully!')
            return redirect('event-detail', pk=event.pk)
        
        elif 'review_form' in request.POST:
            review_form = ReviewForm(request.POST)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.event = event
                review.user = request.user
                review.save()
                messages.success(request, 'Review posted successfully!')
                return redirect('event-detail', pk=event.pk)
    else:
        ticket_form = TicketTypeForm()
        image_form = EventImageForm()
        review_form = ReviewForm()
    
    context = {
        'event': event,
        'is_organizer': is_organizer,
        'ticket_form': ticket_form,
        'image_form': image_form,
        'review_form': review_form,
        'ticket_types': event.ticket_types.all(),
        'images': event.images.all(),
        'reviews': event.reviews.all(),
    }
    return render(request, 'events/event_detail.html', context)

@login_required
def create_event(request):
    if request.method == 'POST':
        event_form = EventForm(request.POST, request.FILES)
        if event_form.is_valid():
            event = event_form.save(commit=False)
            event.organizer = request.user
            event.save()
            messages.success(request, 'Event created successfully! Add images and ticket types.')
            return redirect('event-detail', pk=event.pk)
    else:
        event_form = EventForm()
    
    context = {
        'event_form': event_form,
    }
    return render(request, 'events/create_event.html', context)

@login_required
def add_event_image(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        form = EventImageForm(request.POST, request.FILES)
        if form.is_valid():
            event_image = form.save(commit=False)
            event_image.event = event
            event_image.save()
            messages.success(request, 'Image added successfully!')
            return redirect('event-detail', pk=event.pk)
    else:
        form = EventImageForm()
    
    context = {
        'event': event,
        'form': form,
    }
    return render(request, 'events/add_event_image.html', context)

@login_required
def add_ticket_type(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        form = TicketTypeForm(request.POST)
        if form.is_valid():
            ticket_type = form.save(commit=False)
            ticket_type.event = event
            ticket_type.save()
            messages.success(request, 'Ticket type added successfully!')
            return redirect('event-detail', pk=event.pk)
    else:
        form = TicketTypeForm()
    
    context = {
        'event': event,
        'form': form,
    }
    return render(request, 'events/add_ticket_type.html', context)

@login_required
def dashboard(request):
    user = request.user

    user_events = Event.objects.filter(organizer=user)
    user_bookings = Booking.objects.filter(user=user)

    # Safely count upcoming bookings via Python (not multi-level joins)
    upcoming_count = sum(
        1 for booking in user_bookings if booking.ticket_type.event.start_date >= now()
    )

    # Total ticket quantity instead of booking count
    tickets_count = sum(booking.quantity for booking in user_bookings)

    # Events organized by user
    events_count = user_events.count()

    context = {
        'user_events': user_events,
        'user_bookings': user_bookings,
        'upcoming_count': upcoming_count,
        'tickets_count': tickets_count,
        'events_count': events_count,
    }
    return render(request, 'events/dashboard.html', context)

@login_required
def delete_event_image(request, pk):
    image = get_object_or_404(EventImage, pk=pk)
    if request.method == 'POST':
        if image.event.organizer == request.user:
            image.delete()
            messages.success(request, 'Image deleted successfully!')
        else:
            messages.error(request, 'You are not authorized to delete this image.')
    return redirect('add-event-image', pk=image.event.pk)


@login_required
def my_events(request):
    user_events = Event.objects.filter(organizer=request.user).order_by('-created_at')
    return render(request, 'events/my_events.html', {'user_events': user_events})

@login_required
def my_tickets(request):
    user_bookings = Booking.objects.filter(user=request.user).select_related('ticket_type__event').order_by('-booking_date')
    return render(request, 'events/my_tickets.html', {'user_bookings': user_bookings})

@login_required
def saved_events(request):
    # Assuming you have a ManyToManyField for saved events in your Profile model
    saved_events = request.user.profile.saved_events.all()
    return render(request, 'events/saved_events.html', {'saved_events': saved_events})


@login_required
def save_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    request.user.profile.saved_events.add(event)
    messages.success(request, 'Event saved to your profile!')
    return redirect('event-detail', pk=pk)

@login_required
def unsave_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    request.user.profile.saved_events.remove(event)
    messages.success(request, 'Event removed from saved events.')
    return redirect('event-detail', pk=pk)


@login_required
def update_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    
    # Ensure only the event organizer can update it
    if event.organizer != request.user:
        raise PermissionDenied
    
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully!')
            return redirect('event-detail', pk=event.pk)
    else:
        form = EventForm(instance=event)
    
    return render(request, 'events/update_event.html', {
        'form': form,
        'event': event
    })

@login_required
def delete_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    
    # Ensure only the event organizer can delete it
    if event.organizer != request.user:
        raise PermissionDenied
    
    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Event deleted successfully!')
        return redirect('my-events')
    
    return render(request, 'events/delete_event.html', {'event': event})


@login_required
def delete_event_image(request, pk):
    image = get_object_or_404(EventImage, pk=pk)
    if request.user != image.event.organizer:
        raise PermissionDenied
    
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Image deleted successfully!')
    
    return redirect('event-detail', pk=image.event.pk)


@login_required
def download_ticket(request, booking_id):
    try:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        
        # Design parameters
        WIDTH, HEIGHT = 700, 1000
        PRIMARY_COLOR = (40, 40, 200)  # Navy blue
        SECONDARY_COLOR = (230, 80, 30)  # Orange accent
        BG_COLOR = (248, 248, 255)  # Off-white
        
        # Create base image with modern gradient background
        base = Image.new('RGB', (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(base)
        
        # Add modern header with gradient
        for i in range(100):
            alpha = i/100
            color = tuple(int(PRIMARY_COLOR[j] * (1-alpha) + 255*alpha) for j in range(3))
            draw.line((0, i, WIDTH, i), fill=color)
        
        # Load fonts (use absolute paths in production)
        try:
            font_bold = ImageFont.truetype("arialbd.ttf", 28)
            font_regular = ImageFont.truetype("arial.ttf", 22)
            font_small = ImageFont.truetype("arial.ttf", 18)
        except:
            # Fallback to default fonts
            font_bold = ImageFont.load_default().font_variant(size=28)
            font_regular = ImageFont.load_default().font_variant(size=22)
            font_small = ImageFont.load_default().font_variant(size=18)
        
        # Add event title
        draw.text((WIDTH//2, 60), booking.ticket_type.event.title.upper(), 
                fill="white", font=font_bold, anchor="mt")
        
        # Generate QR code with ticket data
        qr_data = f"""EVENT: {booking.ticket_type.event.title}
DATE: {booking.ticket_type.event.start_date.strftime('%Y-%m-%d %H:%M')}
TICKET ID: {booking.id}
TYPE: {booking.ticket_type.name}
PRICE: ${booking.ticket_type.price:.2f}
QUANTITY: {booking.quantity}"""
        
        qr = qrcode.QRCode(version=1, box_size=6, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=PRIMARY_COLOR, back_color="white")
        
        # Add QR code with stylish border
        qr_size = 300
        qr_position = ((WIDTH - qr_size) // 2, 150)
        base.paste(qr_img.resize((qr_size, qr_size)), qr_position)
        
        # Add decorative elements
        draw.rectangle((50, 500, WIDTH-50, 510), fill=SECONDARY_COLOR)
        
        # Ticket details section
        details = [
            ("DATE", booking.ticket_type.event.start_date.strftime('%b %d, %Y %I:%M %p')),
            ("VENUE", booking.ticket_type.event.location),
            ("TICKET TYPE", booking.ticket_type.name),
            ("QUANTITY", str(booking.quantity)),
            ("PRICE", f"${float(booking.ticket_type.price)*booking.quantity:.2f} TOTAL"),
            ("ORDER ID", f"#{booking.id}"),
            ("ATTENDEE", booking.user.get_full_name() or booking.user.username),
        ]
        
        # Render details with modern layout
        y_pos = 530
        for label, value in details:
            draw.text((100, y_pos), label, fill=(100, 100, 100), font=font_small)
            draw.text((100, y_pos+30), value, fill=(40, 40, 40), font=font_regular)
            y_pos += 80
        
        # Add footer with current date
        draw.text((WIDTH//2, HEIGHT-40), 
                 f"Generated on {datetime.now().strftime('%Y-%m-%d')} • Valid only for this event",
                 fill=(150, 150, 150), font=font_small, anchor="mt")
        
        # Add subtle texture
        try:
            texture = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
            texture_draw = ImageDraw.Draw(texture)
            for i in range(0, WIDTH, 4):
                texture_draw.line((i, 0, i, HEIGHT), fill=(0,0,0,5))
            base = Image.alpha_composite(base.convert('RGBA'), texture).convert('RGB')
        except:
            pass
        
        # Save to buffer
        buffer = BytesIO()
        base.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        
        # Create response
        response = HttpResponse(buffer.getvalue(), content_type="image/png")
        filename = f"ticket_{booking.id}_{datetime.now().strftime('%Y%m%d')}.png"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        print(f"Error generating ticket: {str(e)}", exc_info=True)
        raise Http404(f"Ticket generation failed: {str(e)}")


def about(request):
    return render(request, 'footer/about.html')

def faq(request):
    return render(request, 'footer/faq.html')

def category_list(request):
    categories = Category.objects.annotate(event_count=Count('event')) \
                               .filter(event_count__gt=0) \
                               .order_by('name')
    return render(request, 'events/category_list.html', {'categories': categories})

def organizer_resources(request):
    return render(request, 'footer/organizer_resources.html')

def privacy_policy(request):
    return render(request, 'footer/privacy_policy.html')


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Send email
            send_mail(
                subject=f"Contact Form: {form.cleaned_data['subject']}",
                message=f"From: {form.cleaned_data['name']} <{form.cleaned_data['email']}>\n\n"
                       f"Message:\n{form.cleaned_data['message']}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent successfully!')
            return redirect('contact')
    else:
        form = ContactForm()
    
    return render(request, 'footer/contact.html', {'form': form})