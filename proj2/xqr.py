#!/usr/bin/env python3

#XQR:xborek08
#Author: Martin Borek
#2014

import sys
import argparse
import traceback
import xml.etree.ElementTree as ET
import re

class Params:
    '''Class for handling and parsing given arguments.'''

    def __init__(self):
        self.header = True  # Generate XML header?
        self.output = sys.stdout
        self.xml_input = sys.stdin
        self.query = None
        self.root_element = None # Wraps all results.

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        '''Close files opened in this Params instance.'''

        if self.xml_input != "stdin":
            self.xml_input.close()
        if self.output != "stdout":
            self.output.close()

    def _print_help(self):
        print("""XML Query:
Skript provadi vyhodnoceni zadaneho dotazu, jenz je podobny prikazu SELECT jazyka SQL, nad vstupem ve formatu XML. Vystupem je XML obsahujici elementy splnujici pozadavky dane dotazem.

Parametry:
    --help Napoveda
    --input=filename Vstupni soubor ve formatu XML
    --output=filename Vystupni soubor ve formatu XML s obahem podle zadaneho dotazu
    --query='dotaz' Zadany dotaz (format popsan nize)
    --qf=filename Dotaz (format popsan nize) v externim textovem souboru
    -n Negenerovat XML hlavicku na vystup 
    -root=element Jmeno paroveho korenoveho elementu obalujici vysledky.

Formát dotazu:
    SELECT element LIMIT n FROM element|element.attribute|ROOT WHERE condition
    ORDER BY element|element.attribute ASC|DESC""")

    def _open_input(self, filename):
        '''Opens input file given by filename.'''

        try:
            self.xml_input = open(filename, "r", encoding="utf-8")
        except ValueError:
            raise InputError("Input file encoding is not supported.")
        except:
            raise InputError("Input file couldn't be opened.")
    
    def _open_output(self, filename):
        '''Opens output file given by filename.'''

        try:
            self.output = open(filename, "w", encoding="utf-8")
        except ValueError:
            raise OutputError("Output file encoding is not supported.")
        except:
            raise OutputError("Output file couldn't be opened.")

    def _query_from_param(self, query):
        '''Reads XML query from --query=\'string\'.'''

        self.query = query

    def _query_from_file(self, filename):
        '''Reads XML query from file --qf=filename.'''

        try:
            query_file = open(filename, encoding="utf-8")
        except ValueError:
            raise QueryError("Encoding of file with query is not supported.")
        except:
            raise QueryError("File with query couldn't be opened.")
        self.query = query_file.read()
        query_file.close()

    def _unset_header(self):
        '''Don't print XML header (declaration)'''
        
        self.header = False

    def _set_root_element(self, name):
        '''Name of element wrapping all results'''

        if re.match('\A[a-zA-Z_][a-zA-Z_\-0-9]*\Z' ,name) is None:
            raise ArgError("Wrong root element.")
        self.root_element = name
    
    def get_args(self):
        '''Parses given arguments. May open files for input/input - if given.
        Uses methods defined above.
        '''

        try:
            arg_parser = argparse.ArgumentParser(add_help=False)
            arg_parser.add_argument("--input")
            arg_parser.add_argument("--output")
            exclusive = arg_parser.add_mutually_exclusive_group()
            exclusive.add_argument("--query")
            exclusive.add_argument("--qf")
            arg_parser.add_argument("-n", action="store_true")
            arg_parser.add_argument("--root")
            arg_parser.add_argument("--help", action="store_true") 
            args = arg_parser.parse_args()
        except:
            raise ArgError("Wrong argument(s) entered")
        
        # Count processed arguments to know if an argument is entered more
        # than once.
        argc = 1
        if len(sys.argv) == 1:
            self._print_help()
            raise ArgError("No argument was entered.")
        elif sys.argv[1] == "--help":
            if len(sys.argv) > 2:
                raise ArgError("--help cannot be combined with any other argument.")
            self._print_help()
            exit(0)

        if args.query is None and args.qf is None:
            raise ArgError("Neither --query nor --qf was entered.")
        argc += 1
        if args.query is not None:
            self._query_from_param(args.query)
        else: # --qf 
            self._query_from_file(args.qf)
        if args.n:
            self._unset_header()
            argc += 1
        if args.input is not None:
            self._open_input(args.input)
            argc += 1
        if args.output is not None:
            self._open_output(args.output)
            argc += 1
        if args.root is not None:
            self._set_root_element(args.root)
            argc += 1
        if argc != len(sys.argv):
            raise ArgError("An argument was entered more than once.")


class QueryStates:
    '''States used in Query class FSM when parsing XML query.'''

    BEGIN = 1
    LIMIT = 2
    FROM = 3
    WHERE = 4
    ORDER = 5 
    

class Operators:
    '''Operators in WHERE clause conditions of XML query.'''

    EQUAL = 1
    GREATER = 2
    LESS = 3
    CONTAINS = 4


class Element:
    '''XML Element - only name and attribute. Used for searching.'''

    def __init__(self):
        self.name = None
        self.attribute = None

    def parse(self, element):
        ''' Parses element\'s name and attribute from given string. element is
        a string to parse from. An attribute is separated from a name by "."
        '''

        el_list = element.split('.')
        if len(el_list) == 1:
            if el_list[0] == "":
                return False
            self.name = el_list[0]
        elif len(el_list) == 2:
            if el_list[0] != "":
                self.name = el_list[0]
            self.attribute = el_list[1]
            if self.attribute == "":
                return False
        else:
            return False
        # Check if self.name is a valid XML element name
        if (self.name is not None and re.match('\A[a-zA-Z_][a-zA-Z_\-0-9]*\Z',
                                       self.name) is None):
            raise QueryError("Wrong format of element name.")
        return True


class Condition:
    '''Condition from WHERE clause of XML query.
    Condtitions create a tree. Leafs contain self.element, self.op and
    self.literal for comparison. Other nodes represent "or", "and" and "()".
    If self.parent is None - root element.
    '''
    
    def __init__(self, parent=None):
        '''parent= None ~ root node'''

        self.parent = parent
        self.a = False # and
        self.o = False # or
        self.n = False # not
        self.bracket = False
        self.children = []
        self.element = None
        self.op = None # operator from class Operators
        self.literal = None

    def is_empty(self):
        if self.a or self.o or self.children or self.op is not None:
            return False
        else:
            return True 

       
class Query:
    '''XML query class.
    Parses given XML query and stores its values
    '''

    def __init__(self, query):
        '''query is XML query to parse.'''

        self._stat = QueryStates.BEGIN      
        # Split query into strings by white chars and operators from WHERE
        # clause. These operators must stay in final list.
        self._query = list(filter(None, re.split(r'(>|<|=|\(|\))|\s+', query)))
        self._i = 0 # index to word currently being processed
        self.select = None
        self.limit = None
        self.from_ = None
        self.where = None
        self.order_element = None
        self.order_desc = False

    def parse(self):
        '''This method parses all query. It is a FSM. If IndexError occurs
        FSM expected another string and is not in a final state.'''

        self._i = 0
        try:
            while True:
                if self._stat == QueryStates.BEGIN:
                    if self._query[self._i] != "SELECT":
                        raise QueryError("SELECT is missing.")
                    else:
                        self._i += 1
                        self.select = self._query[self._i]
                        if re.match('\A[a-zA-Z_][a-zA-Z_\-0-9]*\Z',
                                    self.select) is None:
                            raise QueryError("Wrong format of element name.")
                        self._i += 1
                        self._stat = QueryStates.LIMIT
                elif self._stat == QueryStates.LIMIT:
                    if self._query[self._i] == "LIMIT":
                        self._i += 1
                        try:
                            self.limit = int(self._query[self._i])
                        except ValueError:
                            raise QueryError("Expecting an integer after LIMIT.")
                        if self.limit < 0:
                            self.limit = 0 # limit cannot be negative
                        self._i += 1
                    self._stat = QueryStates.FROM
                elif self._stat == QueryStates.FROM:
                    if self._query[self._i] != "FROM":
                        raise QueryError("FROM is missing.")
                    else:
                        self._i += 1
                        if (len(self._query) <= self._i or
                                self._query[self._i] == "WHERE" or
                                (len(self._query) >= self._i and
                                self._query[self._i] == "ORDER" and
                                self._query[self._i + 1] == "BY")):
                            self.from_ = None
                        elif self._query[self._i] == "ROOT":
                            self.from_ = "ROOT"
                            self._i += 1
                        else:
                            self.from_ = Element()
                            result = self.from_.parse(self._query[self._i])
                            self._i += 1
                            if result is False:
                                raise QueryError("Element not correct.")
                        if len(self._query) <= self._i: # correct query
                            break
                        else:
                            self._stat = QueryStates.WHERE
                elif self._stat == QueryStates.WHERE:
                    if self._query[self._i] == "WHERE":
                        self._i += 1
                        self._parse_where()
                    if len(self._query) <= self._i: # correct query
                        break
                    else:
                        self._stat = QueryStates.ORDER
                elif self._stat == QueryStates.ORDER:
                    if (self._query[self._i] == "ORDER"
                        and self._query[self._i + 1] == "BY"):

                        self._i += 2
                        self.order_element = Element()
                        result = self.order_element.parse(self._query[self._i])
                        if result is False:
                            raise QueryError("Element in ORDER not correct.")
                        self._i += 1
                        if self._query[self._i] == "DESC":
                            self.order_desc = True
                        elif self._query[self._i] != "ASC": # wrong ORDER value
                            raise QueryError("Ordering type not recognised.")
                        self._i += 1
                    if self._i < len(self._query):
                        raise QueryError("Contains extra characters.")
                    else:
                        break
        except IndexError:
            raise QueryError("Does not contain all required parts.")
       
    def _parse_where(self):
        '''WHERE clause parsing.
        Creates a tree with conditions self.where.
        '''

        self.where = Condition()
        current = self.where
        brackets = 0
        
        while (self._i < len(self._query)
              and not (self._query[self._i] == "ORDER"
                      and self._query[self._i + 1] == "BY")):
            if self._query[self._i] == "(":
                if not current.is_empty():
                    raise QueryError("Unexpected '(' in WHERE clause.")
                new = Condition(current)
                current.children.append(new)
                current.bracket = True
                current = new
                brackets += 1
                self._i += 1
            elif self._query[self._i] == ")":
                if current.is_empty(): # empty condition: "()"
                    raise QueryError("Unexpected ')' in WHERE clause.")
                current = current.parent
                if not current.bracket:
                    raise QueryError("'(' is missing in WHERE clause.")
                current.bracket = False
                brackets -= 1
                self._i += 1
            elif self._query[self._i] == "NOT":
                if not current.is_empty():
                    raise QueryError("Unexpected 'NOT' in WHERE clause.")
                current.n = False if current.n else True # ternary operator
                self._i += 1
            elif self._query[self._i] == "AND" and not current.is_empty():
                if current.parent is None: # root
                    new = Condition() # new root
                    self.where = new
                    new.a = True
                    new.children.append(current)
                    new_child = Condition(new)
                    new.children.append(new_child)
                    current = new_child
                elif current.parent.o:
                    new = Condition(current.parent) # create a new parent
                    new.a = True
                    new.children.append(current)

                    # Replace a children by its parent
                    current.parent.children.pop() # delete last item in a list
                    current.parent.children.append(new)
                    current.parent = new
                    current = Condition(new)
                    new.children.append(current) # new empty node
                else:
                    current.parent.a = True
                    new = Condition(current.parent)
                    current.parent.children.append(new)
                    current = new
                self._i += 1
            elif self._query[self._i] == "OR" and not current.is_empty():
                if current.parent is None: # root
                    new = Condition() # new root
                    self.where = new
                    new.o = True
                    new.children.append(current)
                    new_child = Condition(new)
                    new.children.append(new_child)
                    current = new_child
                elif current.parent.a:
                    if current.parent.parent is not None:
                        current.parent.parent.o = True
                        new = Condition(current.parent.parent)
                        current.parent.parent.children.append(new)
                        current = new
                    else: # parent is root
                        new = Condition() # new root
                        self.where = new
                        new.o = True
                        new.children.append(current.parent)
                        current.parent.parent = new
                        current = Condition(new)
                        new.children.append(current)
                else:
                    current.parent.o = True
                    new = Condition(current.parent)
                    current.parent.children.append(new)
                    current = new
                self._i += 1
            else:
                if not current.is_empty():
                    raise QueryError("Wrong WHERE clause.")
                current.element = Element()
                result = current.element.parse(self._query[self._i]) # gets Element
                if result is False:
                    raise QueryError("Wrong element in WHERE clause.")
                self._i += 1
                if self._i >= len(self._query):
                    raise QueryError("Relation-operator in WHERE clause missing.")

                if self._query[self._i] == "=":
                    current.op = Operators.EQUAL
                elif self._query[self._i] == ">":
                    current.op = Operators.GREATER
                elif self._query[self._i] == "<":
                    current.op = Operators.LESS
                elif self._query[self._i] == "CONTAINS":
                    current.op = Operators.CONTAINS
                else:
                    raise QueryError("Relation-operator in WHERE clause not found.")
                self._i += 1

                if self._i >= len(self._query):
                    raise QueryError("Literal in WHERE clause missing.")
                try:
                    current.literal = float(self._query[self._i])
                    if current.op == Operators.CONTAINS:
                        raise QueryError("Integer not allowed in CONTAINS WHERE clause.")
                except: # Literal is not a number. Parse string:
                    current.literal = ""
                    if self._query[self._i][0] != '"':
                        raise QueryError("Literal in WHERE clause not found.")
                    # first word, remove '"'
                    current.literal += self._query[self._i][1:]
                    while self._query[self._i][-1] != '"':
                        self._i += 1
                        if self._i >= len(self._query):
                            raise QueryError("Literal in WHERE clause missing.")
                        current.literal += " "
                        current.literal += self._query[self._i]
                    # last word, remove '"' 
                    current.literal = current.literal[:-1] 
                self._i += 1

        # Is any bracket left unclosed?
        # Empty current node means other data was expacted.
        if brackets != 0 or current.is_empty():
            raise QueryError("Wrong WHERE clause.")
    

class SortObject:
    '''Used in XMLParser for sorting nodes when storing strings for
    comparing. node is an ElementTree.Element.
    '''

    def __init__(self, node, string):
        self.node = node
        self.string = string 


class XMLParser:
    '''Element from XML document (xml_input) that meet
    the XML query (class Query).
    '''

    def __init__(self, xml_input):
        self._source = xml_input
        self._elements = []

    def find(self, query):
        '''Finds all elements from self._source that meet
        the XML query (query). Result is stored in self._elements.
        '''

        try:
            tree = ET.parse(self._source)
        except:
            raise FormatError("Given XML is not valid")
        root = tree.getroot()

        if query.from_ is None: # empty output
            return
        elif (query.from_ != "ROOT" and
                root.tag != query.from_.name):
            find_query = ".//"
            if query.from_.name is not None:
                find_query += query.from_.name
            else:
                find_query += "*"
            if query.from_.attribute is not None: 
                find_query += "[@" + query.from_.attribute + "]"
            root = root.find(find_query)
        if root is not None:
            if (query.from_ == "ROOT" and query.select == root.tag and
                    (query.where is None or self._where(root , query.where))):
                self._elements.append(root)

            for element in root.findall(".//" + query.select):
                if (query.where is None or
                        self._where(element, query.where)):
                    self._elements.append(element)

        if query.order_element is not None:
            self._sort(query.order_element, query.order_desc)

        self._limit(query.limit)

    def _limit(self, limit):
        '''LIMIT - takes only first x (limit) elements.'''

        if limit is not None:
            self._elements = self._elements[:limit] 
 
           
    def _sort(self, by, desc=False):
        '''ORDER BY - ordering.
        by is the Element (may include an attribute) to order by.
        Uses class SortObject to store elements with found strings.
        desc says which way to order elements.
        '''

        aux_list = []
        for el in self._elements:

            if by.attribute is None:
                if el.tag == by.name:
                    if len(el) != 0:
                        raise FormatError("Sort: An element contains subelements instead of text")
                    string = el.text
                else:
                    element = el.find(".//" + by.name)
                    if element is None:
                        raise FormatError("Sort: Element not found")
                    if len(element) != 0:
                        raise FormatError("Sort: An element contains subelements instead of text")
                    string = element.text
            else:
                element = None
                if by.name is not None:
                    if el.tag == by.name:
                        element = el.find(".[@" + by.attribute + "]")
                    if element is None: # not found yet, continue searching
                        element = el.find(".//" + by.name + "[@"
                                          + by.attribute + "]")
                        if element is None:
                            raise FormatError("Sort: Element not found")
                else:
                    element = el.find(".[@" + by.attribute + "]") # search root
                    if element is None: # not found yet, continue searching
                        element = el.find(".//*[@" + by.attribute + "]")
                        if element is None:
                            raise FormatError("Sort: Element not found")
                string = element.attrib[by.attribute]

            try: 
                string = float(string) 
            except:
                pass

            sort_object = SortObject(el, string)
            index = 0
            for el_compare in aux_list:
                if string > el_compare.string:                                
                    aux_list.insert(index, sort_object)
                    break;
                index += 1
            else: 
                aux_list.append(sort_object)
        
        self._elements = [] # final result
        index = 1
        for el_final in aux_list:
            if desc:
                el_final.node.set("order", str(len(aux_list) - index + 1))
                self._elements.insert(0, el_final.node)
            else:
                el_final.node.set("order", str(index))
                self._elements.append(el_final.node)
            index += 1

    def write(self, output, root_element, declaration=True):
        '''Writes results (self._elements) to given output.
        root_element wraps all result elements if is not None.
        If declaration is False, declaration header is not included
        in output document.
        '''

        if len(self._elements) == 0 and not root_element:
            root = ET.Element(None)
            if declaration: # include XML declaration
                ET.ElementTree(root).write(output.buffer, encoding="utf-8", xml_declaration=True)
        elif root_element is not None:
            output_root = ET.Element(root_element)
            output_tree = ET.ElementTree(output_root) 
            for el in self._elements:
                output_root.append(el)
            if declaration: # include XML declaration
                output_tree.write(output.buffer, encoding='utf-8', xml_declaration=True)
            else:
                output_tree.write(output.buffer)
        else:
            for el in self._elements:
                output_tree = ET.ElementTree(el) 
                if declaration: # include XML declaration
                    output_tree.write(output.buffer, encoding='utf-8', xml_declaration=True)
                    declaration = False
                else:
                    output_tree.write(output.buffer)


    def _where(self, root, condition):
        '''Does root meet condition? Returns True if so, False otherwise.
        Uses recursion to go to leaf nodes and back.
        '''
        
        # NEG
        if condition.n:
            true = False
            false = True
        else:
            true = True
            false = False

        if condition.o: # OR
            for sub_condition in condition.children:
                if self._where(root, sub_condition):
                    return true
            return false
        elif condition.a: # AND
            for sub_condition in condition.children:
                if not self._where(root, sub_condition):
                    return false
            return true
        elif condition.op is None: # only brackets
            if self._where(root, condition.children[0]):
                return true
            else:
                return false
        else: # leaf node
            if condition.element.attribute is None:
                if root.tag == condition.element.name:
                    if len(root) != 0:
                        raise FormatError("An element contains subelements instead of text")
                    check = root.text
                else:
                    element = root.find(".//" + condition.element.name)
                    if element is None:
                        return false
                    if len(element) != 0:
                        raise FormatError("An element contains subelements instead of text")
                    check = element.text
            else:
                element = None
                if condition.element.name is not None:
                    if root.tag == condition.element.name:
                        element = root.find(".[@" +
                                           condition.element.attribute + "]")
                    if element is None: # not found yet, continue searching

                        element = root.find(".//" +
                                           condition.element.name +
                                           "[@" +
                                           condition.element.attribute + "]")
                        if element is None:
                            return false
                else:
                    element = root.find(".[@" +
                                       condition.element.attribute + "]")
                    if element is None: # not found yet, continue searching
                        element = root.find(".//*[@" + condition.element.attribute + "]")
                        if element is None:
                            return false
                check = element.attrib[condition.element.attribute]
                
            try: # different types in CONDITION clause -> FALSE
                check = float(check)
                if type(condition.literal) != float:
                    return false
            except:
                if type(condition.literal) == float:
                    return false

            # Comparisons of leafs
            if condition.op == Operators.GREATER:
                if check > condition.literal:
                    return true
                else:
                    return false
            elif condition.op == Operators.LESS:
                if check < condition.literal:
                    return true
                else:
                    return false
            elif condition.op == Operators.EQUAL:
                if check == condition.literal:
                    return true
                else:
                    return false
            elif condition.op == Operators.CONTAINS:
                if condition.literal in check:
                    return true
                else:
                    return false
            else:
                raise Exception("Operator missing!")


'''Definition of Error classes:''' 
class QueryError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class ArgError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class InputError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class OutputError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class FormatError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def main():
    '''MAIN PROGRAM'''

    err_code = 0
    try:
        params = Params()
        params.get_args()
        query = Query(params.query)
        query.parse()
        xmlparser = XMLParser(params.xml_input)
        xmlparser.find(query)
        xmlparser.write(params.output, params.root_element, params.header)

    except ArgError as e:
        sys.stderr.write("Arguments error: " + e.value + "\n")
        err_code = 1
    except InputError as e:
        sys.stderr.write("Input error: " + e.value + "\n")
        err_code = 2
    except OutputError as e:
        sys.stderr.write("Output error: " + e.value + "\n")
        err_code = 3
    except FormatError as e:
        sys.stderr.write("Format error: " + e.value + "\n")
        err_code = 4
    except QueryError as e:
        sys.stderr.write("Query error: " + e.value + "\n")
        err_code = 80

    except Exception as e:
        sys.stderr.write(traceback.format_exc())
        err_code = 80
    finally:
        params.cleanup()
        exit(err_code)


main()

