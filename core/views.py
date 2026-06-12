from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.template.loader import get_template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import datetime
from .models import Transaksi, Produk, Pelanggan
from django.db.models import Sum, Q, Count, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal
from io import BytesIO
from xhtml2pdf import pisa
import os
from pathlib import Path
import django
from django.conf import settings as django_settings

def build_laporan_penjualan_queryset(request):
    # Get filter parameters
    status = request.GET.get('status', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Build queryset
    queryset = Transaksi.objects.select_related('idPelanggan').prefetch_related('detail_set__idProduk').order_by('-tanggalTransaksi')
    
    # Apply filters
    if status:
        queryset = queryset.filter(status=status)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            start_dt = timezone.make_aware(start_dt)
            queryset = queryset.filter(tanggalTransaksi__date__gte=start_dt.date())
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = timezone.make_aware(end_dt)
            queryset = queryset.filter(tanggalTransaksi__date__lte=end_dt.date())
        except ValueError:
            pass
    
    # Prepare context
    context_filters = {
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # Calculate summary
    total_transaksi = queryset.count()
    
    # Calculate total pendapatan (only for non-DIBATALKAN status)
    total_pendapatan = 0
    for transaksi in queryset:
        if transaksi.status != 'DIBATALKAN':
            total_pendapatan += float(transaksi.totalTransaksi) + float(transaksi.ongkir)
    
    summary = {
        'total_transaksi': total_transaksi,
        'total_pendapatan': total_pendapatan,
    }
    
    return queryset, context_filters, summary


@staff_member_required
def admin_laporan_penjualan(request):
    queryset, context_filters, summary = build_laporan_penjualan_queryset(request)
    
    # Prepare data for template
    transaksi_data = []
    for i, transaksi in enumerate(queryset, 1):
        # Format products
        produk_list = []
        for detail in transaksi.detail_set.all():
            produk_nama = detail.idProduk.namaProduk
            produk_jumlah = detail.jumlahProduk
            produk_list.append(f"{produk_nama} ({produk_jumlah})")
        produk_str = ", ".join(produk_list)
        
        total_akhir = float(transaksi.totalTransaksi) + float(transaksi.ongkir)
        
        transaksi_data.append({
            'no': i,
            'tanggal': transaksi.tanggalTransaksi.strftime('%d/%m/%Y'),
            'pelanggan': transaksi.idPelanggan.namaPelanggan,
            'produk': produk_str,
            'ongkir': transaksi.ongkir,
            'total_akhir': total_akhir,
            'status': transaksi.get_status_display(),
        })
    
    context = {
        'transaksi_data': transaksi_data,
        'filters': context_filters,
        'summary': summary,
        'status_choices': Transaksi.STATUS_CHOICES,
    }
    
    return render(request, 'admin/laporan_penjualan.html', context)


@staff_member_required
def admin_laporan_penjualan_pdf(request):
    queryset, context_filters, summary = build_laporan_penjualan_queryset(request)
    
    # Prepare data for template
    transaksi_data = []
    for i, transaksi in enumerate(queryset, 1):
        # Format products
        produk_list = []
        for detail in transaksi.detail_set.all():
            produk_nama = detail.idProduk.namaProduk
            produk_jumlah = detail.jumlahProduk
            produk_list.append(f"{produk_nama} ({produk_jumlah})")
        produk_str = ", ".join(produk_list)
        
        total_akhir = float(transaksi.totalTransaksi) + float(transaksi.ongkir)
        
        transaksi_data.append({
            'no': i,
            'tanggal': transaksi.tanggalTransaksi.strftime('%d/%m/%Y'),
            'pelanggan': transaksi.idPelanggan.namaPelanggan,
            'produk': produk_str,
            'ongkir': transaksi.ongkir,
            'total_akhir': total_akhir,
            'status': transaksi.get_status_display(),
        })
    
    context = {
        'transaksi_data': transaksi_data,
        'filters': context_filters,
        'summary': summary,
        'status_choices': Transaksi.STATUS_CHOICES,
        'today': timezone.now().strftime('%d/%m/%Y'),
    }
    
    template_path = 'admin/laporan_penjualan_pdf.html'
    template = get_template(template_path)
    html = template.render(context)
    
    # Create a PDF
    buffer = BytesIO()
    
    # Define link callback for static files
    def link_callback(uri, rel):
        import os
        from django.conf import settings
        
        # Handle static files
        if uri.startswith('/static/'):
            # Convert /static/... to the actual static file path
            static_path = uri.replace('/static/', '').lstrip('/')
            for static_dir in settings.STATICFILES_DIRS:
                path = os.path.join(str(static_dir), static_path)
                if os.path.exists(path):
                    return path
            # If not found in STATICFILES_DIRS, try STATIC_ROOT
            path = os.path.join(str(settings.STATIC_ROOT), static_path)
            return path
        elif uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '', 1))
            return path
        return uri
    
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8', link_callback=link_callback)
    
    # If error then show some funy view
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    
    # Return PDF response
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laporan_penjualan.pdf"'
    
    return response


def build_laporan_produk_queryset(request):
    status = request.GET.get('status', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    transaksi_filter = Q(detailtransaksi__idTransaksi__status__in=[
    'MENUNGGU_VERIFIKASI', 'DISETUJUI', 'DIKIRIM', 'SELESAI', 'REFUND_SELESAI'
    ])

    if status:
        transaksi_filter = Q(detailtransaksi__idTransaksi__status=status)

    if start_date:
        try:
            sd = datetime.strptime(start_date, '%Y-%m-%d').date()
            transaksi_filter &= Q(detailtransaksi__idTransaksi__tanggalTransaksi__date__gte=sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, '%Y-%m-%d').date()
            transaksi_filter &= Q(detailtransaksi__idTransaksi__tanggalTransaksi__date__lte=ed)
        except ValueError:
            pass

    qs = Produk.objects.all().annotate(
        kuantitas_terjual=Coalesce(
            Sum('detailtransaksi__jumlahProduk', filter=transaksi_filter),
            0
        )
    ).order_by('namaProduk')

    filters = {
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
    }

    return qs, filters


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_produk(request):
    qs, filters = build_laporan_produk_queryset(request)

    produk_data = []
    for i, p in enumerate(qs, 1):
        produk_data.append({
            'no': i,
            'nama': p.namaProduk,
            'harga': p.hargaProduk,
            'stok': p.stok,
            'terjual': p.kuantitas_terjual,
        })

    context = {
        'produk_data': produk_data,
        'filters': filters,
       
    }
    return render(request, 'admin/laporan_produk.html', context)


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_produk_pdf(request):
    qs, filters = build_laporan_produk_queryset(request)

    produk_data = []
    for i, p in enumerate(qs, 1):
        produk_data.append({
            'no': i,
            'nama': p.namaProduk,
            'harga': p.hargaProduk,
            'stok': p.stok,
            'terjual': p.kuantitas_terjual,
        })

    context = {
        'produk_data': produk_data,
        'filters': filters,
        'today': timezone.now().strftime('%d/%m/%Y'),
    }

    template = get_template('admin/laporan_produk_pdf.html')
    html = template.render(context)

    buffer = BytesIO()
    def link_callback(uri, rel):
        import os
        from django.conf import settings
        
        if uri.startswith('/static/'):
            static_path = uri.replace('/static/', '').lstrip('/')
            for static_dir in settings.STATICFILES_DIRS:
                path = os.path.join(str(static_dir), static_path)
                if os.path.exists(path):
                    return path
            path = os.path.join(str(settings.STATIC_ROOT), static_path)
            return path
        elif uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '', 1))
            return path
        return uri
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8')

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laporan_produk.pdf"'
    return response


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_pelanggan(request):
    # Get all customers with their transaction statistics
    pelanggan_qs = Pelanggan.objects.all().annotate(
        total_transaksi_selesai=Count(
            'transaksi_set',
            filter=Q(transaksi_set__status='SELESAI')
        ),
        total_pengeluaran=Coalesce(
            Sum(
                ExpressionWrapper(
                    F('transaksi_set__totalTransaksi') + F('transaksi_set__ongkir'),
                    output_field=DecimalField(max_digits=14, decimal_places=2)
                ),
                filter=Q(transaksi_set__status='SELESAI')
            ),
            Decimal('0.00'),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    ).order_by('namaPelanggan')

    # Prepare data for template
    pelanggan_data = []
    for i, pelanggan in enumerate(pelanggan_qs, 1):
        pelanggan_data.append({
            'no': i,
            'nama': pelanggan.namaPelanggan,
            'jml_transaksi': pelanggan.total_transaksi_selesai,
            'total_pengeluaran': float(pelanggan.total_pengeluaran) if pelanggan.total_pengeluaran else 0,
        })

    context = {
        'pelanggan_data': pelanggan_data,
    }
    
    return render(request, 'admin/laporan_pelanggan.html', context)


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_pelanggan_pdf(request):
    # Get all customers with their transaction statistics
    pelanggan_qs = Pelanggan.objects.all().annotate(
        total_transaksi_selesai=Count(
            'transaksi_set',
            filter=Q(transaksi_set__status='SELESAI')
        ),
        total_pengeluaran=Coalesce(
            Sum(
                ExpressionWrapper(
                    F('transaksi_set__totalTransaksi') + F('transaksi_set__ongkir'),
                    output_field=DecimalField(max_digits=14, decimal_places=2)
                ),
                filter=Q(transaksi_set__status='SELESAI')
            ),
            Decimal('0.00'),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    ).order_by('namaPelanggan')

    # Prepare data for template
    pelanggan_data = []
    for i, pelanggan in enumerate(pelanggan_qs, 1):
        pelanggan_data.append({
            'no': i,
            'nama': pelanggan.namaPelanggan,
            'jml_transaksi': pelanggan.total_transaksi_selesai,
            'total_pengeluaran': float(pelanggan.total_pengeluaran) if pelanggan.total_pengeluaran else 0,
        })

    # Calculate summary
    total_pelanggan = len(pelanggan_data)
    total_pengeluaran_semua = sum(item['total_pengeluaran'] for item in pelanggan_data)

    context = {
        'pelanggan_data': pelanggan_data,
        'today': timezone.now().strftime('%d/%m/%Y'),
        'summary': {
            'total_pelanggan': total_pelanggan,
            'total_pengeluaran_semua': total_pengeluaran_semua,
        }
    }

    template = get_template('admin/laporan_pelanggan_pdf.html')
    html = template.render(context)

    buffer = BytesIO()
    
    # Use the global link_callback function
    def link_callback(uri, rel):
        import os
        from django.conf import settings
        
        if uri.startswith('/static/'):
            static_path = uri.replace('/static/', '').lstrip('/')
            for static_dir in settings.STATICFILES_DIRS:
                path = os.path.join(str(static_dir), static_path)
                if os.path.exists(path):
                    return path
            path = os.path.join(str(settings.STATIC_ROOT), static_path)
            return path
        elif uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '', 1))
            return path
        return uri
    
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8', link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laporan_pelanggan.pdf"'
    return response
