from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from googleapiclient.errors import HttpError

from core.app_Gestor import drive_repository as repo


class _FakeHttpResp:
    """httplib2.Response é dict-like -- HttpError acessa .get()/.reason dele."""
    def __init__(self, status):
        self.status = status
        self.reason = f'status {status}'

    def get(self, key, default=None):
        return default


def _http_error(status):
    return HttpError(_FakeHttpResp(status), b'{}')


class _FlakyExecutable:
    """Simula uma requisição que falha N vezes com um HttpError antes de
    ter sucesso (ou falha sempre, se fail_times for grande o suficiente)."""
    def __init__(self, fail_times, status=429, result=None):
        self.fail_times = fail_times
        self.status = status
        self.result = result if result is not None else {'ok': True}
        self.calls = 0

    def execute(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _http_error(self.status)
        return self.result


class _FakeExecutable:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeCreateExecutable:
    """Espelha _FlakyExecutable, mas também captura o body/media_body do
    upload no sucesso -- para exercitar upload_file() através do retry de
    verdade (_execute_with_retry), não só a chamada em si."""
    def __init__(self, fake_service, body, media_body, fields, fail_times, status):
        self._service = fake_service
        self._body = body
        self._media_body = media_body
        self._fields = fields
        self._fail_times = fail_times
        self._status = status
        self.calls = 0

    def execute(self):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise _http_error(self._status)
        self._service.create_calls += 1
        self._service.created_bodies.append(self._body)
        if self._media_body is not None:
            self._service.uploaded_content = self._media_body.getbytes(0, self._media_body.size())
            self._service.uploaded_mimetype = self._media_body.mimetype()
        result = {'id': self._service.next_id}
        if 'webViewLink' in self._fields:
            result['webViewLink'] = f'https://drive.google.com/file/{self._service.next_id}'
        return result


class _FakeFiles:
    def __init__(self, fake_service):
        self._service = fake_service

    def list(self, q, fields, supportsAllDrives=True, includeItemsFromAllDrives=True):
        self._service.list_calls += 1
        self._service.last_query = q
        return _FakeExecutable({'files': self._service.list_result})

    def create(self, body, fields, media_body=None, supportsAllDrives=True):
        return _FakeCreateExecutable(
            self._service, body, media_body, fields,
            self._service.create_fail_times, self._service.create_fail_status,
        )

    def delete(self, fileId, supportsAllDrives=True):
        if self._service.delete_error is not None:
            raise self._service.delete_error
        self._service.delete_calls += 1
        self._service.deleted_ids.append(fileId)
        return _FakeExecutable({})

    def get_media(self, fileId, supportsAllDrives=True):
        self._service.get_media_calls += 1
        if self._service.get_media_error is not None:
            raise self._service.get_media_error
        return _FakeExecutable(self._service.media_content)


class FakeDriveService:
    """In-memory substituto da service resource retornada por googleapiclient build()."""

    def __init__(
        self, list_result=None, next_id='FILE-1', media_content=b'',
        create_fail_times=0, create_fail_status=429,
        delete_error=None, get_media_error=None,
    ):
        self.list_result = list_result or []
        self.next_id = next_id
        self.media_content = media_content
        self.create_fail_times = create_fail_times
        self.create_fail_status = create_fail_status
        self.delete_error = delete_error
        self.get_media_error = get_media_error
        self.list_calls = 0
        self.create_calls = 0
        self.delete_calls = 0
        self.get_media_calls = 0
        self.created_bodies = []
        self.deleted_ids = []
        self.last_query = None
        self.uploaded_content = None
        self.uploaded_mimetype = None

    def files(self):
        return _FakeFiles(self)


@override_settings(GOOGLE_DRIVE_ROOT_FOLDER_ID='ROOT-1')
class DriveRepositoryTestCase(SimpleTestCase):

    def use_fake_service(self, **kwargs):
        fake = FakeDriveService(**kwargs)
        patcher = patch.object(repo, '_get_service', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake


class GetOrCreateClientFolderTests(DriveRepositoryTestCase):

    def test_returns_existing_folder_id_when_found(self):
        fake = self.use_fake_service(list_result=[{'id': 'FOLDER-EXISTING'}])

        folder_id = repo.get_or_create_client_folder('CLI-1', 'Ana Silva')

        self.assertEqual(folder_id, 'FOLDER-EXISTING')
        self.assertEqual(fake.create_calls, 0)

    def test_creates_folder_inside_root_when_not_found(self):
        fake = self.use_fake_service(list_result=[], next_id='FOLDER-NEW')

        folder_id = repo.get_or_create_client_folder('CLI-1', 'Ana Silva')

        self.assertEqual(folder_id, 'FOLDER-NEW')
        self.assertEqual(fake.create_calls, 1)
        self.assertEqual(fake.created_bodies[0]['name'], 'CLI-1 - Ana Silva')
        self.assertEqual(fake.created_bodies[0]['parents'], ['ROOT-1'])
        self.assertEqual(fake.created_bodies[0]['mimeType'], 'application/vnd.google-apps.folder')

    @override_settings(GOOGLE_DRIVE_ROOT_FOLDER_ID='')
    def test_raises_when_root_folder_not_configured(self):
        self.use_fake_service()

        with self.assertRaises(repo.DriveNotConfiguredError):
            repo.get_or_create_client_folder('CLI-1', 'Ana Silva')

    def test_folder_name_with_apostrophe_is_escaped_in_query(self):
        # Nome de cliente tipo "D'Angelo" quebraria a query do Drive (que usa
        # aspas simples como delimitador) se não for escapado.
        fake = self.use_fake_service(list_result=[])

        repo.get_or_create_client_folder('CLI-1', "D'Angelo")

        self.assertIn("D\\'Angelo", fake.last_query)
        self.assertNotIn("'D'Angelo'", fake.last_query)

    def test_search_is_scoped_to_root_folder_and_excludes_trashed(self):
        fake = self.use_fake_service(list_result=[])

        repo.get_or_create_client_folder('CLI-1', 'Ana Silva')

        self.assertIn("'ROOT-1' in parents", fake.last_query)
        self.assertIn('trashed = false', fake.last_query)
        self.assertIn("mimeType = 'application/vnd.google-apps.folder'", fake.last_query)


class UploadFileTests(DriveRepositoryTestCase):

    def test_uploads_into_folder_and_returns_id_and_link(self):
        fake = self.use_fake_service(next_id='FILE-1')

        result = repo.upload_file('FOLDER-1', 'doc.pdf', b'conteudo', 'application/pdf')

        self.assertEqual(result['id'], 'FILE-1')
        self.assertEqual(result['webViewLink'], 'https://drive.google.com/file/FILE-1')
        self.assertEqual(fake.created_bodies[0]['name'], 'doc.pdf')
        self.assertEqual(fake.created_bodies[0]['parents'], ['FOLDER-1'])

    def test_uploads_exact_bytes_and_mimetype(self):
        fake = self.use_fake_service(next_id='FILE-1')

        repo.upload_file('FOLDER-1', 'doc.pdf', b'conteudo binario aqui', 'application/pdf')

        self.assertEqual(fake.uploaded_content, b'conteudo binario aqui')
        self.assertEqual(fake.uploaded_mimetype, 'application/pdf')

    def test_upload_retries_on_transient_error_and_succeeds(self):
        fake = self.use_fake_service(next_id='FILE-1', create_fail_times=2, create_fail_status=503)

        with patch.object(repo.time, 'sleep'):
            result = repo.upload_file('FOLDER-1', 'doc.pdf', b'conteudo', 'application/pdf')

        self.assertEqual(result['id'], 'FILE-1')
        self.assertEqual(fake.create_calls, 1)

    def test_upload_propagates_storage_quota_exceeded_without_retry(self):
        # Regressao do bug real encontrado em producao: service account sem
        # Shared Drive recebe 403 storageQuotaExceeded, e isso NAO e
        # transitorio -- upload_file precisa deixar o erro subir, nao
        # engolir nem ficar tentando de novo.
        self.use_fake_service(create_fail_times=1, create_fail_status=403)

        with patch.object(repo.time, 'sleep') as mock_sleep:
            with self.assertRaises(HttpError):
                repo.upload_file('FOLDER-1', 'doc.pdf', b'conteudo', 'application/pdf')

        mock_sleep.assert_not_called()

    def test_upload_gives_up_after_max_retries_on_persistent_429(self):
        self.use_fake_service(create_fail_times=99, create_fail_status=429)

        with patch.object(repo.time, 'sleep'):
            with self.assertRaises(HttpError):
                repo.upload_file('FOLDER-1', 'doc.pdf', b'conteudo', 'application/pdf')


class DownloadDeleteFileTests(DriveRepositoryTestCase):

    def test_download_returns_raw_bytes(self):
        self.use_fake_service(media_content=b'conteudo do arquivo')

        self.assertEqual(repo.download_file('FILE-1'), b'conteudo do arquivo')

    def test_download_propagates_error_when_file_missing(self):
        self.use_fake_service(get_media_error=_http_error(404))

        with self.assertRaises(HttpError):
            repo.download_file('FILE-nope')

    def test_delete_calls_api_with_given_file_id(self):
        fake = self.use_fake_service()

        repo.delete_file('FOLDER-1')

        self.assertEqual(fake.deleted_ids, ['FOLDER-1'])

    def test_delete_propagates_error_on_failure(self):
        self.use_fake_service(delete_error=_http_error(404))

        with self.assertRaises(HttpError):
            repo.delete_file('FILE-nope')


class GetServiceTests(SimpleTestCase):
    """_get_service() é a única função que fala com a Google API de verdade
    (auth via credentials.json) -- aqui só validamos o cache/erro, sem rede."""

    def setUp(self):
        patcher = patch.object(repo, '_service', None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_raises_file_not_found_when_credentials_missing(self):
        with patch.object(repo.os.path, 'exists', return_value=False):
            with self.assertRaises(FileNotFoundError):
                repo._get_service()

    def test_builds_service_once_and_caches_it(self):
        fake_service = object()
        with patch.object(repo.os.path, 'exists', return_value=True), \
             patch.object(repo.service_account.Credentials, 'from_service_account_file', return_value=object()), \
             patch.object(repo, 'build', return_value=fake_service) as mock_build:
            first = repo._get_service()
            second = repo._get_service()

        self.assertIs(first, fake_service)
        self.assertIs(second, fake_service)
        mock_build.assert_called_once()


class ExecuteWithRetryTests(SimpleTestCase):

    def test_succeeds_immediately_without_error(self):
        request = _FlakyExecutable(fail_times=0)

        result = repo._execute_with_retry(request)

        self.assertEqual(result, {'ok': True})
        self.assertEqual(request.calls, 1)

    def test_retries_on_429_and_eventually_succeeds(self):
        request = _FlakyExecutable(fail_times=2, status=429)

        with patch.object(repo.time, 'sleep') as mock_sleep:
            result = repo._execute_with_retry(request)

        self.assertEqual(result, {'ok': True})
        self.assertEqual(request.calls, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_gives_up_after_max_retries(self):
        request = _FlakyExecutable(fail_times=99, status=429)

        with patch.object(repo.time, 'sleep'):
            with self.assertRaises(HttpError):
                repo._execute_with_retry(request, max_retries=3)

        self.assertEqual(request.calls, 4)  # tentativa inicial + 3 retries

    def test_does_not_retry_non_transient_status(self):
        request = _FlakyExecutable(fail_times=1, status=404)

        with patch.object(repo.time, 'sleep') as mock_sleep:
            with self.assertRaises(HttpError):
                repo._execute_with_retry(request)

        self.assertEqual(request.calls, 1)
        mock_sleep.assert_not_called()
