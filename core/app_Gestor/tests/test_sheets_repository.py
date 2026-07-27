import re
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.app_Gestor import sheets_repository as repo

_RANGE_RE = re.compile(r'^([^!]+)!A(\d+):[A-Z]+\d+$')


class _FakeExecutable:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeValues:
    def __init__(self, fake_service):
        self._service = fake_service

    def get(self, spreadsheetId, range):
        self._service.get_calls += 1
        rows = self._service.tabs.get(range, [])
        return _FakeExecutable({'values': [list(row) for row in rows]})

    def append(self, spreadsheetId, range, valueInputOption, insertDataOption, body):
        self._service.append_calls += 1
        self._service.tabs.setdefault(range, []).extend(
            list(row) for row in body['values']
        )
        return _FakeExecutable({})

    def update(self, spreadsheetId, range, valueInputOption, body):
        self._service.update_calls += 1
        match = _RANGE_RE.match(range)
        tab, row_number = match.group(1), int(match.group(2))
        self._service.tabs[tab][row_number - 1] = list(body['values'][0])
        return _FakeExecutable({})


class _FakeSpreadsheets:
    def __init__(self, fake_service):
        self._service = fake_service

    def values(self):
        return _FakeValues(self._service)

    def get(self, spreadsheetId):
        self._service.metadata_calls += 1
        sheets = [
            {'properties': {'title': title, 'sheetId': sheet_id}}
            for title, sheet_id in self._service.sheet_ids.items()
        ]
        return _FakeExecutable({'sheets': sheets})

    def batchUpdate(self, spreadsheetId, body):
        self._service.batch_update_calls += 1
        drop = body['requests'][0]['deleteDimension']
        sheet_id = drop['range']['sheetId']
        start, end = drop['range']['startIndex'], drop['range']['endIndex']
        tab = next(t for t, sid in self._service.sheet_ids.items() if sid == sheet_id)
        del self._service.tabs[tab][start:end]
        return _FakeExecutable({})


class FakeSheetsService:
    """In-memory substituto da service resource retornada por googleapiclient build()."""

    def __init__(self, tabs, sheet_ids=None):
        self.tabs = {tab: [list(row) for row in rows] for tab, rows in tabs.items()}
        self.sheet_ids = sheet_ids or {tab: idx for idx, tab in enumerate(tabs)}
        self.get_calls = 0
        self.append_calls = 0
        self.update_calls = 0
        self.batch_update_calls = 0
        self.metadata_calls = 0

    def spreadsheets(self):
        return _FakeSpreadsheets(self)


CLIENTES_HEADER = ['id', 'atualizado_em', 'nome', 'email']


def _clientes_fixture():
    return {
        'Clientes': [
            CLIENTES_HEADER,
            ['CLI-aaaaaaaa', '2024-01-01T00:00:00+00:00', 'Ana', 'ana@old.com'],
            ['CLI-bbbbbbbb', '2024-01-02T00:00:00+00:00', 'Bruno', 'bruno@x.com'],
        ]
    }


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class SheetsRepositoryTestCase(SimpleTestCase):
    """Base: isola o cache global do repositório entre testes e injeta o fake service."""

    def setUp(self):
        repo._cache.clear()
        self.addCleanup(repo._cache.clear)

    def use_fake_service(self, tabs, sheet_ids=None):
        fake = FakeSheetsService(tabs, sheet_ids=sheet_ids)
        patcher = patch.object(repo, '_get_service', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake


class ColLetterTests(SimpleTestCase):

    def test_first_columns_are_single_letters(self):
        self.assertEqual(repo._col_letter(0), 'A')
        self.assertEqual(repo._col_letter(25), 'Z')

    def test_columns_past_z_use_double_letters(self):
        self.assertEqual(repo._col_letter(26), 'AA')
        self.assertEqual(repo._col_letter(27), 'AB')


class NewIdTests(SimpleTestCase):

    def test_known_tabs_use_their_prefix(self):
        self.assertTrue(repo._new_id('Clientes').startswith('CLI-'))
        self.assertTrue(repo._new_id('Parceiros').startswith('PAR-'))
        self.assertTrue(repo._new_id('Precos').startswith('PRC-'))

    def test_unknown_tab_falls_back_to_row_prefix(self):
        self.assertTrue(repo._new_id('OutraAba').startswith('ROW-'))

    def test_ids_are_unique(self):
        self.assertNotEqual(repo._new_id('Clientes'), repo._new_id('Clientes'))


class ListRowsTests(SheetsRepositoryTestCase):

    def test_returns_rows_as_dicts_keyed_by_header(self):
        self.use_fake_service(_clientes_fixture())

        rows = repo.list_rows('Clientes')

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {
            'id': 'CLI-aaaaaaaa',
            'atualizado_em': '2024-01-01T00:00:00+00:00',
            'nome': 'Ana',
            'email': 'ana@old.com',
        })

    def test_empty_tab_returns_empty_list(self):
        self.use_fake_service({'Clientes': []})

        self.assertEqual(repo.list_rows('Clientes'), [])

    @override_settings(GOOGLE_SHEETS_CACHE_TTL_SECONDS=20)
    def test_second_call_within_ttl_is_served_from_cache(self):
        fake = self.use_fake_service(_clientes_fixture())

        with patch.object(repo.time, 'monotonic', side_effect=[0.0, 5.0]):
            repo.list_rows('Clientes')
            repo.list_rows('Clientes')

        self.assertEqual(fake.get_calls, 1)

    @override_settings(GOOGLE_SHEETS_CACHE_TTL_SECONDS=20)
    def test_call_after_ttl_expiry_refetches(self):
        fake = self.use_fake_service(_clientes_fixture())

        with patch.object(repo.time, 'monotonic', side_effect=[0.0, 25.0, 25.0]):
            repo.list_rows('Clientes')
            repo.list_rows('Clientes')

        self.assertEqual(fake.get_calls, 2)


class GetRowTests(SheetsRepositoryTestCase):

    def test_returns_matching_row(self):
        self.use_fake_service(_clientes_fixture())

        row = repo.get_row('Clientes', 'CLI-bbbbbbbb')

        self.assertEqual(row['nome'], 'Bruno')

    def test_returns_none_when_not_found(self):
        self.use_fake_service(_clientes_fixture())

        self.assertIsNone(repo.get_row('Clientes', 'CLI-nao-existe'))


class CreateRowTests(SheetsRepositoryTestCase):

    def test_generates_id_and_timestamp_and_appends_in_header_order(self):
        fake = self.use_fake_service(_clientes_fixture())

        created = repo.create_row('Clientes', {'nome': 'Carla', 'email': 'carla@x.com'})

        self.assertTrue(created['id'].startswith('CLI-'))
        self.assertIn('atualizado_em', created)
        appended_row = fake.tabs['Clientes'][-1]
        self.assertEqual(appended_row, [created['id'], created['atualizado_em'], 'Carla', 'carla@x.com'])

    def test_invalidates_cache_so_next_read_sees_new_row(self):
        fake = self.use_fake_service(_clientes_fixture())
        repo.list_rows('Clientes')
        get_calls_before = fake.get_calls

        # create_row também lê a aba (sem cache) só para pegar o cabeçalho,
        # então o contador sobe mais de 1 aqui -- o que importa é a leitura
        # seguinte não vir do cache antigo.
        repo.create_row('Clientes', {'nome': 'Carla', 'email': 'carla@x.com'})
        get_calls_after_create = fake.get_calls
        rows = repo.list_rows('Clientes')

        self.assertGreater(get_calls_after_create, get_calls_before)
        self.assertEqual(fake.get_calls, get_calls_after_create + 1)
        self.assertEqual(len(rows), 3)

    def test_raises_when_tab_has_no_header(self):
        self.use_fake_service({'Clientes': []})

        with self.assertRaises(ValueError):
            repo.create_row('Clientes', {'nome': 'Carla'})


class UpdateRowTests(SheetsRepositoryTestCase):

    def test_updates_only_the_targeted_row(self):
        fake = self.use_fake_service(_clientes_fixture())

        repo.update_row('Clientes', 'CLI-bbbbbbbb', {'email': 'bruno@novo.com'})

        self.assertEqual(fake.tabs['Clientes'][1][3], 'ana@old.com')  # linha da Ana intacta
        updated_row = fake.tabs['Clientes'][2]
        self.assertEqual(updated_row[2], 'Bruno')  # campo não enviado é preservado
        self.assertEqual(updated_row[3], 'bruno@novo.com')

    def test_bumps_atualizado_em(self):
        self.use_fake_service(_clientes_fixture())

        result = repo.update_row('Clientes', 'CLI-bbbbbbbb', {'email': 'bruno@novo.com'})

        self.assertNotEqual(result['atualizado_em'], '2024-01-02T00:00:00+00:00')

    def test_invalidates_cache(self):
        fake = self.use_fake_service(_clientes_fixture())
        repo.list_rows('Clientes')
        get_calls_before = fake.get_calls

        repo.update_row('Clientes', 'CLI-bbbbbbbb', {'email': 'bruno@novo.com'})
        get_calls_after_update = fake.get_calls
        repo.list_rows('Clientes')

        self.assertGreater(get_calls_after_update, get_calls_before)
        self.assertEqual(fake.get_calls, get_calls_after_update + 1)

    def test_raises_lookup_error_when_row_missing(self):
        self.use_fake_service(_clientes_fixture())

        with self.assertRaises(LookupError):
            repo.update_row('Clientes', 'CLI-nao-existe', {'email': 'x@x.com'})

    def test_matching_expected_atualizado_em_succeeds(self):
        self.use_fake_service(_clientes_fixture())

        result = repo.update_row(
            'Clientes', 'CLI-bbbbbbbb', {'email': 'bruno@novo.com'},
            expected_atualizado_em='2024-01-02T00:00:00+00:00',
        )

        self.assertEqual(result['email'], 'bruno@novo.com')

    def test_stale_expected_atualizado_em_raises_concurrency_error_without_writing(self):
        fake = self.use_fake_service(_clientes_fixture())

        with self.assertRaises(repo.ConcurrencyError):
            repo.update_row(
                'Clientes', 'CLI-bbbbbbbb', {'email': 'bruno@novo.com'},
                expected_atualizado_em='2024-01-02T99:99:99+00:00',
            )

        self.assertEqual(fake.update_calls, 0)
        self.assertEqual(fake.tabs['Clientes'][2][3], 'bruno@x.com')


class DeleteRowTests(SheetsRepositoryTestCase):

    def test_removes_the_row_from_the_sheet(self):
        fake = self.use_fake_service(_clientes_fixture(), sheet_ids={'Clientes': 42})

        repo.delete_row('Clientes', 'CLI-aaaaaaaa')

        remaining_ids = [row[0] for row in fake.tabs['Clientes'][1:]]
        self.assertEqual(remaining_ids, ['CLI-bbbbbbbb'])
        self.assertEqual(fake.batch_update_calls, 1)

    def test_invalidates_cache(self):
        fake = self.use_fake_service(_clientes_fixture(), sheet_ids={'Clientes': 42})
        repo.list_rows('Clientes')
        get_calls_before = fake.get_calls

        repo.delete_row('Clientes', 'CLI-aaaaaaaa')
        get_calls_after_delete = fake.get_calls
        repo.list_rows('Clientes')

        self.assertGreater(get_calls_after_delete, get_calls_before)
        self.assertEqual(fake.get_calls, get_calls_after_delete + 1)

    def test_raises_lookup_error_when_row_missing(self):
        self.use_fake_service(_clientes_fixture(), sheet_ids={'Clientes': 42})

        with self.assertRaises(LookupError):
            repo.delete_row('Clientes', 'CLI-nao-existe')

    def test_raises_lookup_error_when_tab_missing_from_metadata(self):
        self.use_fake_service(_clientes_fixture(), sheet_ids={'Outra': 99})

        with self.assertRaises(LookupError):
            repo.delete_row('Clientes', 'CLI-aaaaaaaa')


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
