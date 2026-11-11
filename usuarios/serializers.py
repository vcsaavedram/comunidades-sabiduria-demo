from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.files.storage import default_storage
from .models import Usuario, PerfilCliente, PerfilOrganizador, DocumentoKYC

# Sub-documentos embebidos
class DocumentoKYCSerializer(serializers.Serializer):
    """Valida cada documento legal dentro del arreglo documentos_kyc."""
    tipo_documento = serializers.CharField(max_length=50)
    ruta_archivo = serializers.CharField(max_length=255)
    estado = serializers.CharField(max_length=50, default="pendiente_revision", read_only=True)

class AuditoriaIdentidadSerializer(serializers.Serializer):
    """Estructura de lectura del sub-documento único de revisión interna."""
    revisado_por_admin_id = serializers.CharField(max_length=100, allow_null=True, required=False)
    fecha_verificacion = serializers.DateTimeField(allow_null=True, required=False)
    comentarios_revision = serializers.CharField(allow_blank=True, required=False)

# Registrar usuario
class RegistroClienteSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    nombres = serializers.CharField(max_length=100)
    apellidos = serializers.CharField(max_length=100)
    nombre_a_mostrar = serializers.CharField(max_length=100, required=False, allow_blank=True)
    fecha_nacimiento = serializers.DateField()
    telefono = serializers.CharField(max_length=25, required=False, allow_blank=True)
    descripcion = serializers.CharField(required=False, allow_blank=True)
    foto_perfil = serializers.ImageField(required=False, allow_null=True)
    intereses = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)
    habilidades = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)

    def validate_correo(self, value):
        if Usuario.objects.filter(correo=value.lower()).exists():
            raise serializers.ValidationError("Ya existe una cuenta registrada con este correo electrónico.")
        return value.lower()

    def create(self, validated_data):
        correo = validated_data.pop('correo')
        password = validated_data.pop('password')

        if not validated_data.get('nombre_a_mostrar'):
            validated_data['nombre_a_mostrar'] = validated_data['nombres'].split()[0]

        usuario = Usuario.objects.create_user(correo=correo, password=password, rol='cliente')
        perfil = PerfilCliente.objects.create(usuario=usuario, **validated_data)
        return perfil

class RegistroOrganizadorSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    persona_natural = serializers.BooleanField(default=True)
    nombres = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    apellidos = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    razon_social = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    nombre_a_mostrar = serializers.CharField(max_length=100, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=25, required=False, allow_blank=True)
    descripcion = serializers.CharField(required=False, allow_blank=True)
    foto_perfil = serializers.ImageField(required=False, allow_null=True)

    def validate_correo(self, value):
        if Usuario.objects.filter(correo=value.lower()).exists():
            raise serializers.ValidationError("Ya existe una cuenta registrada con este correo electrónico.")
        return value.lower()

    def validate(self, data):
        if data.get('persona_natural', True):
            if not (data.get('nombres') and data.get('apellidos')):
                raise serializers.ValidationError({
                    "nombres": "Nombres y apellidos son obligatorios si te registras como persona natural."
                })
            data['razon_social'] = None
            if not data.get('nombre_a_mostrar'):
                data['nombre_a_mostrar'] = f"{data['nombres']} {data['apellidos']}"
        else:
            if not data.get('razon_social'):
                raise serializers.ValidationError({
                    "razon_social": "La razón social es obligatoria para organizaciones o empresas."
                })
            data['nombres'] = None
            data['apellidos'] = None
            if not data.get('nombre_a_mostrar'):
                data['nombre_a_mostrar'] = data['razon_social']
        return data

    def create(self, validated_data):
        correo = validated_data.pop('correo')
        password = validated_data.pop('password')

        usuario = Usuario.objects.create_user(correo=correo, password=password, rol='organizador')
        perfil = PerfilOrganizador.objects.create(
            usuario=usuario,
            estado_validacion="pendiente",
            **validated_data
        )
        return perfil

# Iniciar sesión
class LoginSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        correo = data.get('correo', '').lower()
        password = data.get('password', '')

        if correo and password:
            usuario = authenticate(request=self.context.get('request'), username=correo, password=password)
            if not usuario:
                raise serializers.ValidationError(
                    "El correo o la contraseña no coinciden. Por favor, revísalos con calma e intenta de nuevo."
                )
        else:
            raise serializers.ValidationError("Por favor, ingresa tu correo y tu contraseña para entrar.")

        data['usuario'] = usuario
        return data

# Visualizar perfil
class VerPerfilClienteSerializer(serializers.ModelSerializer):
    """Vista de perfil del Cliente: oculta correo, teléfono y contraseña por privacidad."""
    fecha_registro = serializers.DateTimeField(source='usuario.fecha_registro', read_only=True)

    class Meta:
        model = PerfilCliente
        fields = [
            'id', 'nombres', 'apellidos', 'nombre_a_mostrar',
            'descripcion', 'fecha_nacimiento', 'foto_perfil',
            'intereses', 'habilidades', 'fecha_registro'
        ]

class VerPerfilOrganizadorSerializer(serializers.ModelSerializer):
    """Vista de perfil del Organizador: muestra correo y teléfono de contacto; oculta clave y KYC."""
    correo = serializers.EmailField(source='usuario.correo', read_only=True)
    fecha_registro = serializers.DateTimeField(source='usuario.fecha_registro', read_only=True)

    class Meta:
        model = PerfilOrganizador
        fields = [
            'id', 'correo', 'telefono', 'persona_natural', 'nombres', 'apellidos',
            'razon_social', 'nombre_a_mostrar', 'descripcion', 'foto_perfil',
            'estado_validacion', 'fecha_registro'
        ]

# Edición de perfil
class BaseEditarPerfilSerializer(serializers.ModelSerializer):
    """Clase padre que permite a ambos roles editar su correo, su contraseña (con PBKDF2 + Sal) y reemplazar o eliminar su foto de perfil limpiando archivos antiguos del disco."""
    correo = serializers.EmailField(source='usuario.correo', required=False)
    fecha_registro = serializers.DateTimeField(source='usuario.fecha_registro', read_only=True)

    password_actual = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    nueva_password = serializers.CharField(write_only=True, required=False, min_length=8, style={'input_type': 'password'})

    def validate_correo(self, value):
        correo_limpio = value.lower().strip()
        usuario_actual = self.instance.usuario
        if Usuario.objects.filter(correo=correo_limpio).exclude(pk=usuario_actual.pk).exists():
            raise serializers.ValidationError("Este correo electrónico ya está siendo utilizado por otra cuenta.")
        return correo_limpio

    def validate_credenciales(self, data):
        nueva_password = data.get('nueva_password')
        password_actual = data.get('password_actual')

        if nueva_password:
            if not password_actual:
                raise serializers.ValidationError({
                    "password_actual": "Por seguridad, debes escribir tu contraseña actual para poder cambiarla."
                })
            if not self.instance.usuario.check_password(password_actual):
                raise serializers.ValidationError({
                    "password_actual": "Tu contraseña actual no coincide. Intenta escribirla de nuevo."
                })
        return data

    def actualizar_usuario_base_y_foto(self, instance, validated_data):
        # 1. Actualizar correo y/o contraseña en colección Usuario (si fueron enviados)
        usuario_data = validated_data.pop('usuario', {})
        nuevo_correo = usuario_data.get('correo')
        nueva_password = validated_data.pop('nueva_password', None)
        validated_data.pop('password_actual', None)

        usuario = instance.usuario
        hubo_cambios_auth = False

        if nuevo_correo and nuevo_correo != usuario.correo:
            usuario.correo = nuevo_correo
            hubo_cambios_auth = True

        if nueva_password:
            usuario.set_password(nueva_password)
            hubo_cambios_auth = True

        if hubo_cambios_auth:
            usuario.save()

        # 2. Si el usuario sube una nueva foto_perfil o la borra (envía null), limpiamos la antigua del disco
        if 'foto_perfil' in validated_data and instance.foto_perfil:
            instance.foto_perfil.delete(save=False)


class EditarPerfilClienteSerializer(BaseEditarPerfilSerializer):
    """Permite al Cliente modificar TODOS sus campos: correo, contraseña, nombres, apellidos, nombre_a_mostrar, descripcion, telefono, fecha_nacimiento, foto_perfil, intereses y habilidades."""
    class Meta:
        model = PerfilCliente
        fields = [
            'id', 'correo', 'telefono', 'password_actual', 'nueva_password',
            'nombres', 'apellidos', 'nombre_a_mostrar', 'descripcion',
            'fecha_nacimiento', 'foto_perfil', 'intereses', 'habilidades',
            'fecha_registro'
        ]

    def validate(self, data):
        return self.validate_credenciales(data)

    def update(self, instance, validated_data):
        self.actualizar_usuario_base_y_foto(instance, validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class EditarPerfilOrganizadorSerializer(BaseEditarPerfilSerializer):
    """Permite al Organizador modificar TODOS sus campos: correo, contraseña, persona_natural, nombres, apellidos, razon_social, nombre_a_mostrar, descripcion, telefono, foto_perfil y documentos_kyc."""
    auditoria_identidad_interna = AuditoriaIdentidadSerializer(read_only=True)
    documentos_kyc = DocumentoKYCSerializer(many=True, required=False)

    # Campos para subir o reemplazar un archivo físico KYC desde el computador (FormData)
    nuevo_archivo_kyc = serializers.FileField(write_only=True, required=False)
    nuevo_tipo_documento = serializers.CharField(write_only=True, max_length=50, required=False)

    class Meta:
        model = PerfilOrganizador
        fields = [
            'id', 'correo', 'telefono', 'password_actual', 'nueva_password',
            'persona_natural', 'nombres', 'apellidos', 'razon_social',
            'nombre_a_mostrar', 'descripcion', 'foto_perfil',
            'estado_validacion', 'documentos_kyc', 'nuevo_archivo_kyc',
            'nuevo_tipo_documento', 'auditoria_identidad_interna', 'fecha_registro'
        ]
        read_only_fields = ['estado_validacion', 'auditoria_identidad_interna']

    def validate(self, data):
        data = self.validate_credenciales(data)

        if data.get('nuevo_archivo_kyc') and not data.get('nuevo_tipo_documento'):
            raise serializers.ValidationError({
                "nuevo_tipo_documento": "Debes indicar qué tipo de documento estás subiendo (ej: RUT, Antecedentes)."
            })

        persona_natural = data.get('persona_natural', getattr(self.instance, 'persona_natural', True))
        nombres = data.get('nombres', getattr(self.instance, 'nombres', None))
        apellidos = data.get('apellidos', getattr(self.instance, 'apellidos', None))
        razon_social = data.get('razon_social', getattr(self.instance, 'razon_social', None))

        if persona_natural:
            if not (nombres and apellidos):
                raise serializers.ValidationError({
                    "detalle": "Para personas naturales, los nombres y apellidos son obligatorios."
                })
            data['razon_social'] = None
        else:
            if not razon_social:
                raise serializers.ValidationError({
                    "detalle": "Para organizaciones o empresas, la razón social es obligatoria."
                })
            data['nombres'] = None
            data['apellidos'] = None

        return data

    def update(self, instance, validated_data):
        self.actualizar_usuario_base_y_foto(instance, validated_data)

        # Opción A: Si envía la lista de documentos_kyc por JSON (para editar o quitar un documento de la lista)
        docs_data = validated_data.pop('documentos_kyc', None)
        if docs_data is not None:
            instance.documentos_kyc = [DocumentoKYC(**doc) for doc in docs_data]

        # Opción B: Si sube un archivo físico nuevo (PDF/Imagen) por FormData
        archivo_kyc = validated_data.pop('nuevo_archivo_kyc', None)
        tipo_doc = validated_data.pop('nuevo_tipo_documento', None)
        if archivo_kyc and tipo_doc:
            ruta_guardada = default_storage.save(f"perfiles/kyc/{instance.usuario.pk}_{archivo_kyc.name}", archivo_kyc)
            nuevo_doc_bson = DocumentoKYC(
                tipo_documento=tipo_doc,
                ruta_archivo=ruta_guardada,
                estado="pendiente_revision"
            )
            docs_actuales = [d for d in (instance.documentos_kyc or []) if d.tipo_documento != tipo_doc]
            docs_actuales.append(nuevo_doc_bson)
            instance.documentos_kyc = docs_actuales
            instance.estado_validacion = "pendiente"

        # Actualiza todos los demás campos enviados (nombres, razon_social, telefono, descripcion, etc.)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance