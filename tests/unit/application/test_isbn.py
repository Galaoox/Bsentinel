import pytest

from bsentinel.domain.isbn import normalize_isbn


@pytest.mark.parametrize('value,expected', [
    ('978-0-132-35088-4', '9780132350884'), (' 0 8044 2957 x ', '080442957X'),
    ('0132350882', '0132350882'), ('9780132350884', '9780132350884'),
    ('9780132350885', None), ('0132350883', None), ('19780132350884', None),
    ('97801323508840', None), ('ISBN:9780132350884', None), ('', None), (None, None),
])
def test_normalize_isbn_validates_whole_value_and_checksum(value, expected):
    assert normalize_isbn(value) == expected
