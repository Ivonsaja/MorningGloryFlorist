from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from decimal import Decimal
import os

class Pelanggan(models.Model):
    idPelanggan = models.AutoField(primary_key=True)
    namaPelanggan = models.CharField(max_length=50)
    username = models.CharField(max_length=50, unique=True)
    passwordHash = models.CharField(max_length=128)
    alamat = models.TextField(blank=True)
    nomorTelepon = models.CharField(max_length=20, blank=True)
    
    def set_password(self, raw_password):
        self.passwordHash = make_password(raw_password)
    
    def check_password(self, raw_password):
        return check_password(raw_password, self.passwordHash)
    
    def __str__(self):
        return f"{self.idPelanggan} - {self.namaPelanggan} ({self.username})"
    
    class Meta:
        verbose_name = "Pelanggan"
        verbose_name_plural = "Pelanggan"

class Kurir(models.Model):
    idKurir = models.AutoField(primary_key=True)
    namaKurir = models.CharField(max_length=50)
    noHp = models.CharField(max_length=20)
    username = models.CharField(max_length=50, unique=True)
    passwordHash = models.CharField(max_length=128)
    
    def set_password(self, raw_password):
        self.passwordHash = make_password(raw_password)
    
    def check_password(self, raw_password):
        return check_password(raw_password, self.passwordHash)
    
    def __str__(self):
        return f"{self.idKurir} - {self.namaKurir}"
    
    class Meta:
        verbose_name = "Kurir"
        verbose_name_plural = "Kurir"

class Produk(models.Model):
    idProduk = models.AutoField(primary_key=True)
    namaProduk = models.CharField(max_length=50)
    hargaProduk = models.DecimalField(max_digits=12, decimal_places=2)
    stok = models.PositiveIntegerField(default=0)
    deskripsi = models.TextField(blank=True)
    foto = models.ImageField(upload_to='produk/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.idProduk} - {self.namaProduk} (Rp{self.hargaProduk})"
    
    class Meta:
        verbose_name = "Produk"
        verbose_name_plural = "Produk"

class Transaksi(models.Model):
    STATUS_CHOICES = [
        ('MENUNGGU_VERIFIKASI', 'Menunggu Verifikasi'),
        ('DISETUJUI', 'Disetujui'),
        ('DIKIRIM', 'Dikirim'),
        ('SELESAI', 'Selesai'),
        ('DIBATALKAN', 'Dibatalkan'),
        ('REFUND_SELESAI', 'Refund Selesai'),
    ]
    
    idTransaksi = models.AutoField(primary_key=True)
    idPelanggan = models.ForeignKey(Pelanggan, on_delete=models.CASCADE, related_name='transaksi_set')
    idKurir = models.ForeignKey(Kurir, on_delete=models.SET_NULL, null=True, blank=True, related_name='transaksi_set')
    tanggalTransaksi = models.DateTimeField(auto_now_add=True)
    alamatPengiriman = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='MENUNGGU_VERIFIKASI')
    catatan = models.TextField(blank=True)
    buktiBayar = models.ImageField(upload_to='bukti_bayar/', blank=True, null=True)
    tanggalVerifikasi = models.DateTimeField(null=True, blank=True)
    catatanPembayaran = models.TextField(blank=True)
    buktiSampai = models.ImageField(upload_to='bukti_sampai/', blank=True, null=True)
    
    # Refund fields
    bankRefund = models.CharField(max_length=50, blank=True)
    rekeningRefund = models.CharField(max_length=40, blank=True)
    buktiRefund = models.ImageField(upload_to='bukti_refund/', blank=True, null=True)
    tanggalRefund = models.DateTimeField(null=True, blank=True)
    catatanRefund = models.TextField(blank=True)
    ongkir = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    totalTransaksi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def hitung_total(self):
        total = Decimal('0')
        for detail in self.detail_set.all():
            total += detail.subTotal
        return total
    
    def update_total(self):
        self.totalTransaksi = self.hitung_total()
        self.save(update_fields=['totalTransaksi'])
    

    
    def set_status(self, new_status):
        old_status = self.status
        self.status = new_status
        
        # Handle stock changes
        if new_status == 'DIBATALKAN':
            # Restore stock and delete details to prevent double restoration
            for detail in self.detail_set.all():
                produk = detail.idProduk
                produk.stok += detail.jumlahProduk
                produk.save()
            # Delete all details to prevent stock restoration on subsequent saves
            self.detail_set.all().delete()
        
        # Update verification date
        if new_status in ['DISETUJUI', 'DIBATALKAN']:
            from django.utils import timezone
            self.tanggalVerifikasi = timezone.now()
        
        self.save()
    
    def save(self, *args, **kwargs):
        # Run validation
        self.full_clean()
        
        # Detect if this is a new object
        is_new = self.pk is None
        
        # Save first
        super().save(*args, **kwargs)
        
        # Handle stock management for new transactions
        active_statuses = ['MENUNGGU_VERIFIKASI', 'DISETUJUI', 'DIKIRIM', 'SELESAI']
        if (is_new and 
            self.status in active_statuses and 
            self.detail_set.exists()):
            # Deduct stock for new transaction
            for detail in self.detail_set.all():
                produk = detail.idProduk
                if produk.stok < detail.jumlahProduk:
                    raise ValidationError(f"Stok {produk.namaProduk} tidak mencukupi")
                produk.stok -= detail.jumlahProduk
                produk.save()
    
    def clean(self):
        # Validate payment proof for active statuses
        active_statuses = ['MENUNGGU_VERIFIKASI', 'DISETUJUI', 'DIKIRIM', 'SELESAI']
        if self.status in active_statuses and not self.buktiBayar:
            raise ValidationError("Bukti bayar wajib diunggah untuk status aktif")
        
        # Validate refund proof
        if self.status == 'REFUND_SELESAI':
            if not self.buktiRefund:
                raise ValidationError("Bukti refund wajib diunggah untuk status Refund Selesai")
            if not self.tanggalRefund:
                raise ValidationError("Tanggal refund wajib diisi untuk status Refund Selesai")
        
        # Validate shipping address
        if not self.alamatPengiriman:
            raise ValidationError("Alamat pengiriman wajib diisi")
    
    def __str__(self):
        return f"{self.idTransaksi} - {self.idPelanggan.namaPelanggan} ({self.status})"
    
    class Meta:
        verbose_name = "Transaksi"
        verbose_name_plural = "Transaksi"

class DetailTransaksi(models.Model):
    idDetail = models.AutoField(primary_key=True)
    idTransaksi = models.ForeignKey(Transaksi, on_delete=models.CASCADE, related_name='detail_set')
    idProduk = models.ForeignKey(Produk, on_delete=models.CASCADE)
    jumlahProduk = models.PositiveIntegerField()
    hargaSatuanSaatTransaksi = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    subTotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def save(self, *args, **kwargs):
        if not self.hargaSatuanSaatTransaksi:
            self.hargaSatuanSaatTransaksi = self.idProduk.hargaProduk
        
        self.subTotal = Decimal(self.jumlahProduk) * self.hargaSatuanSaatTransaksi
        super().save(*args, **kwargs)
        
        # Update transaction total
        self.idTransaksi.update_total()
    
    def __str__(self):
        return f"{self.idDetail} - {self.idProduk.namaProduk} x{self.jumlahProduk}"
    
    class Meta:
        verbose_name = "Detail Transaksi"
        verbose_name_plural = "Detail Transaksi"
