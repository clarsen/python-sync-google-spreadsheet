class SheetAdapter(object):
    """
    Interface to a particular google spreadsheet that supports the operations
    needed to append or update rows.

    It's intended that this class be specialized so that row_to_key and
    non_empty_column parameters don't need to be passed in.
    """

    def __init__(self, sheet, start_row_for_updatable, row_to_key,
                 non_empty_column=None):
        # type: (gspread.Spreadsheet) -> None
        """
        If non_empty_column specified, then if the value in that column name is
        empty, that row is considered empty for appending.  Otherwise each
        column in the row must be blank to be considered empty for append.
        """

        self.sheet = sheet
        self.columns = sheet.col_count
        self.rows = sheet.row_count
        self.next_empty_row = None
        self.start_row_for_updatable = start_row_for_updatable
        self.non_empty_column = non_empty_column
        self.row_to_key = row_to_key

        self.column_name_to_column = {}
        self.column_to_column_name = {}
        self.row_for_key = {}
        self.cell_list = None
        if self.non_empty_column is None:
            raise Exception("Must specify non_empty_column")

    def load(self):
        """load in Spreadsheet"""
        # Get headers
        headers = self.sheet.range(1, 1,
                                   2, self.columns)
        for column in range(self.columns):
            self.column_name_to_column[headers[column].value] = column
            self.column_to_column_name[column] = headers[column].value

        # get updatable portion
        self.cell_list = self.sheet.range(self.start_row_for_updatable, 1,
                                          self.rows,
                                          self.columns)
        if self.non_empty_column is not None:
            self.non_empty_column_idx = \
                self.column_name_to_column[self.non_empty_column]

        for row in range(1, self.rows):
            # empty?
            if self.non_empty_column:
                if self.cell_at(row, self.non_empty_column_idx).value == '':
                    self.next_empty_row = row
                    break
            else:
                raise Exception("Must specify non_empty_column")
            key = self.row_to_key(self.row_as_dict(row))
            if key in self.row_for_key:
                raise Exception("Key must be unique")
            self.row_for_key[key] = row
        if self.next_empty_row is None:
            self.next_empty_row = self.rows + 1

    def cell_at(self, row, col):
        return self.cell_list[self.columns * row + col]

    def row_as_dict(self, row):
        # type: (int) -> Dict[str,Any]
        cols = {}
        for col in range(self.columns):
            cname = self.column_to_column_name[col]
            cols[cname] = self.cell_at(row, col).value
        return cols

    def row(self, idx):
        # type: (int) -> Dict[str,Any]
        """Row for index"""
        return self.row_as_dict(idx)

    def append(self, kvhash):
        # type: (Dict[str,Any]) -> None
        """
        Add to sheet a row specified by dictionary
        """
        print("would add to row {}".format(self.next_empty_row))
        row = self.next_empty_row
        for key in kvhash.keys():
            col = self.column_name_to_column[key]
            self.cell_at(row, col).value = kvhash[key]
        self.next_empty_row += 1

    def update_row(self, idx, kvhash, cols_to_update):
        # type: (int, Dict[str,Any], List[str]) -> None
        """
        Update row using dictionary to fill in updated values
        """
        for key in cols_to_update:
            col = self.column_name_to_column[key]
            self.cell_at(idx, col).value = kvhash[key]

    def has(self, kvhash):
        # type: (Dict[str, Any]) -> bool
        """whether kvhash found in spreadsheet using row_for_kvhash matching"""
        key = self.row_to_key(kvhash)
        return key in self.row_for_key

    def row_for_kvhash(self, kvhash):
        # type: (Dict[str, Any]) -> int
        """index of row where kvhash mapped with key_for_rowdict matches"""
        key = self.row_to_key(kvhash)
        return self.row_for_key[key]

    def row_for_colval(self, key, value):
        # type: (str, Any) -> int
        """
        Row index that has column name 'key' with a particular value.
        """
        pass

    def sync(self):
        # type: () -> None
        """Write updated sheet"""
        self.sheet.update_cells(self.cell_list)
