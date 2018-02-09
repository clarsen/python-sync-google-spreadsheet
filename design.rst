What this really focuses around is start_row_for_merging an input of key/values
into an existing spreadsheet from a stream of rows represented as dictionaries.

##############
Data scrubbing
##############

::

  stream function:
    input: csv file
    output: stream of key/value

::

  annotate function:
    output: stream of key/value
    input: stream of key/value

######################################################
Making the spreadsheet workable for iteration/updating
######################################################

::

  spreadsheet adapter:
    input: google spreadsheet
    input: starting row for updatable part of sheet # large updates fail w/ google API
    input: row_to_key function

    row(idx) -> kvhash  # key/value of row
    row_for_colval(value) -> int  # idx of row containing col == value, i.e. a keyed lookup
    append(kvhash):  # add to right after last non-blank row
    update_row(idx, kvhash):  # set col values based on kvhash
    has(kvhash): # using row_to_key function, check presence
    row_for_kvhash(kvhash) -> int # idx of row matching row_to_key

::

  spreadsheet as database:
    with spreadsheet adapter member, extend/add methods
    provide row_to_key function specific to spreadsheet.

    row(idx) -> kvhash: # passed through

    has(kvhash) function: # pass through

    append(kvhash)  # passed through

    update(kvhash) function:
        eventually parameterize this by column name and comparison functions (what gets updated)
        use row_for_kvhash
        use update_row

#########
The merge
#########

::

  merge function:
    destination: spreadsheet as database
    recent_data: stream of key/value

    for kvhash in recent_data:
      if not destination.has(kvhash):
         destination.append(d)
      else:
         destination.update(d)
    destination.sync()

####
BUGS
####

- CSV input that is malformed is not caught
