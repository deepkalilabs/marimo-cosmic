import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# dropdown""")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    # Single selection dropdown
    dropdown1 = mo.ui.dropdown(
        options=["Option 1", "Option 2", "Option 3"], value="Option 1"
    )

    # Searchable dropdown
    dropdown2 = mo.ui.dropdown(
        options=["Red", "Blue", "Green", "Yellow"],
        value="Yellow",
        searchable=True,
    )

    # Searchable dropdown, with deselect
    dropdown3 = mo.ui.dropdown(
        options=["Red", "Blue", "Green", "Yellow"],
        value="Yellow",
        searchable=True,
        allow_select_none=True,
    )

    # Dropdown with dictionary
    dropdown4 = mo.ui.dropdown(
        options={"A": 1, "B": 2, "C": 3}, value="A", allow_select_none=True
    )
    return dropdown1, dropdown2, dropdown3, dropdown4


@app.cell
def _(dropdown1, dropdown2, dropdown3, dropdown4):
    [
        dropdown1,
        dropdown2,
        dropdown3,
        dropdown4,
    ]
    return


@app.cell
def _(mo):
    # Virtualized
    mo.ui.dropdown(
        options=[str(i) for i in range(1000)],
        value=None,
        searchable=True,
        allow_select_none=True,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# multiselect""")
    return


@app.cell
def _(mo):
    # multiselect
    multiselect1 = mo.ui.multiselect(
        options=["Option 1", "Option 2", "Option 3"], value=["Option 1"]
    )


    # mutliselect of 1
    multiselect2 = mo.ui.multiselect(
        options=["Red", "Blue", "Green", "Yellow"],
        max_selections=1,
    )

    # multiselect with dictionary
    multiselect3 = mo.ui.multiselect(options={"A": 1, "B": 2, "C": 3}, value=["A"])

    # multiselec with max 2
    multiselect4 = mo.ui.multiselect(
        options=["Cat", "Dog", "Bird"], value=None, max_selections=2
    )
    return multiselect1, multiselect2, multiselect3, multiselect4


@app.cell
def _(multiselect1, multiselect2, multiselect3, multiselect4):
    [
        multiselect1,
        multiselect2,
        multiselect3,
        multiselect4,
    ]
    return


if __name__ == "__main__":
    app.run()
