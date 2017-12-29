class SheetAdapter(object):
    """
    Interface to a particular google spreadsheet that supports the operations
    needed to append or update rows.

    It's intended that this class be specialized for the particular sheet.
    """
    def __init__(self, sheet):
        # type: (gspread.Spreadsheet) -> None
        self.sheet = sheet

    def load(self):
        """load in Spreadsheet"""
        pass

    def sync(self):
        # type: () -> None
        """Write updated sheet"""
        pass

    def exists(self, key):
        # type: (str) -> bool
        """Does key exist in sheet?"""
        pass

    def value(self, key):
        # type: (str) -> Any
        """Value for key in sheet"""
        pass

    def append(self, key, values):
        # type: (str, Dict[str,Any]) -> None
        """
        Add to sheet a row for key, with other column values specified by
        dictionary
        """
        pass

    def update(self, key, value):
        # type: (str, Any) -> None
        """
        Update row for particular key, with new value specified by value
        """
        pass
