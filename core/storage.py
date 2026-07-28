from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class NonStrictManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Adiciona hash de conteúdo ao nome dos estáticos (cache-busting) quando
    o manifesto existe (gerado por `collectstatic`). Se o manifesto ainda não
    foi gerado -- ex: `runserver` local sem rodar `collectstatic` antes --
    cai de volta pro caminho sem hash em vez de derrubar o template com
    ValueError."""

    manifest_strict = False
