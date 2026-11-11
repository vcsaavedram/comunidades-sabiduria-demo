from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django_mongodb_backend.models import EmbeddedModel
from django_mongodb_backend.fields import ArrayField, EmbeddedModelField, EmbeddedModelArrayField

# Modelos embebios
class DocumentoKYC(EmbeddedModel):
    """Sub-documento BSON para los archivos legales del organizador."""
    tipo_documento = models.CharField(max_length=50)
    ruta_archivo = models.CharField(max_length=255)
    estado = models.CharField(max_length=50, default="pendiente_revision")

class AuditoriaIdentidad(EmbeddedModel):
    """Sub-documento BSON de auditoría interna (Reemplaza a Autentikar)."""
    revisado_por_admin_id = models.CharField(max_length=100, null=True, blank=True)
    fecha_verificacion = models.DateTimeField(null=True, blank=True)
    comentarios_revision = models.TextField(blank=True)

# Colección usuarios
class UsuarioManager(BaseUserManager):
    def create_user(self, correo, password=None, **extra_fields):
        if not correo:
            raise ValueError('Campo correo obligatorio')
        user = self.model(correo=self.normalize_email(correo), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

class Usuario(AbstractBaseUser):
    ROLES = (
        ('cliente', 'Cliente'),
        ('organizador', 'Organizador')
    )
    correo = models.EmailField(unique=True)
    rol = models.CharField(max_length=20, choices=ROLES, default='cliente')
    is_active = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()
    USERNAME_FIELD = 'correo'

    def __str__(self):
        return f"{self.correo} ({self.rol})"

# Colección clientes
class PerfilCliente(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='perfil_cliente')
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    nombre_a_mostrar = models.CharField(max_length=100, blank=True)
    fecha_nacimiento = models.DateField()
    foto_perfil = models.ImageField(upload_to='perfiles/clientes/', null=True, blank=True)
    descripcion = models.TextField(blank=True)
    telefono = models.CharField(max_length=25, blank=True)

    intereses = ArrayField(
        models.CharField(max_length=50),
        default=list, 
        blank=True
    )
    habilidades = ArrayField(
        models.CharField(max_length=50),
        default=list, 
        blank=True
    )

    def __str__(self):
        return f"Perfil Cliente: {self.nombres} {self.apellidos}"

# Colección Organizadores
class PerfilOrganizador(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='perfil_organizador')
    nombres = models.CharField(max_length=100, null=True, blank=True)
    apellidos = models.CharField(max_length=100, null=True, blank=True)
    nombre_a_mostrar = models.CharField(max_length=100, blank=True)
    descripcion = models.TextField(blank=True)
    telefono = models.CharField(max_length=25, blank=True)
    foto_perfil = models.ImageField(upload_to='perfiles/organizadores/', null=True, blank=True)
    persona_natural = models.BooleanField(default=True)
    razon_social = models.CharField(max_length=150, null=True, blank=True)
    estado_validacion = models.CharField(max_length=50, default="pendiente")

    auditoria_identidad_interna = EmbeddedModelField(embedded_model=AuditoriaIdentidad, null=True, blank=True)
    documentos_kyc = EmbeddedModelArrayField(embedded_model=DocumentoKYC, default=list, blank=True)

    def __str__(self):
        return f"Perfil Org: {self.razon_social or self.nombres}"