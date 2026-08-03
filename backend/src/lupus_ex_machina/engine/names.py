"""Bank of first names.

Players never choose their own name: it is drawn for them, which removes a bias
and closes a prompt injection vector (D-042). The names are French because they
are shown on screen and read by the models (HR-6).
"""

FIRST_NAMES: tuple[str, ...] = (
    "Adèle",
    "Armand",
    "Basile",
    "Camille",
    "Céleste",
    "Clovis",
    "Diane",
    "Émile",
    "Faustine",
    "Gaspard",
    "Hélène",
    "Isaure",
    "Jonas",
    "Léonie",
    "Marius",
    "Noé",
    "Olympe",
    "Perrine",
    "Quentin",
    "Rosalie",
    "Sylvain",
    "Thelma",
    "Ulysse",
    "Violette",
)
