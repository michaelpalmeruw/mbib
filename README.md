# mbib
Bibliography manager for Linux, for use with both LaTeX and OpenOffice/Libreoffice,
capable of handling large databases with ease

Features:

- Import from and export to BibTex

- Import records from DOI and PubMed identifiers

- Push citations to Texmaker/TexStudio

- Push citations to OpenOffice.org/LibreOffice. Advanced formatting of bibliographies piggybacks on JabRef. Thus, you need to have JabRef installed in order to fully use mbib with OOo/LO

- Written in Python3

- Console-based GUI, based on the urwid and urwidtrees Python libraries

- Data are stored in a SQLite database


Status: the code is reasonably complete and working. The documentation has a fairly thorough
tutorial that covers most topics, but the reference part is missing.

If you want to try it out, here is a brief Howto:

- clone the repository, or download the zip archive and unzip it

- make sure the mbib directory is in your bash $PATH, and the mbib.sh script inside it is executable

- install the prerequisites: Python3, the urwid, urwidtrees, lxml, and requests Python3 packages; xsel

- open a shell window and run mbib.sh

