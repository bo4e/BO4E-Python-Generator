from bo4e_generator.schema import camel_to_snake


class TestSchema:
    def test_camel_to_snake(self) -> None:
        camelcasestring = "LastgangKompakt"
        snakecasestring = "lastgang_kompakt"
        assert snakecasestring == camel_to_snake(camelcasestring)
