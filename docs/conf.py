# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


# sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


project = "ReQJS"
copyright = "2026, Bart Lengkeek"
author = "Bart Lengkeek"
release = "0.1b"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

autodoc_preserve_defaults = True
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
copybutton_exclude = ".linenos, .gp"
maximum_signature_line_length = 95

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"  # "python_docs_theme" # "sphinx_rtd_theme"
html_static_path = ["_static"]
