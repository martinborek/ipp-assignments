<?php

#JMP:xborek08

/**
  File: jmp.php
  Date: 16. 3. 2014
  Author: Martin Borek, xborek08@stud.fit.vutbr.cz
  Project: Simple makroprocessor; first project for IPP course
*/

  error_reporting(0);

  mb_internal_encoding("utf-8"); // nastaveni kodovani

  define("SUCCESS", 0);

  /** Hodnoty chyb programu */
  abstract class ERRORS {

    const params = 1;
    const input = 2;
    const output = 3;
    const inputFormat = 4;
    const syntax = 55;
    const semantics = 56;
    const redef = 57;

  }

  /** Typy maker */
  abstract class MACROS {
    
    const normal = 0;
    const def = 1;
    const let = 2;
    const set = 3;
    const nul = 4;
  }

  /** Objekt makra */
  class Macro {
    
    public $argc; // pocet argumentu
    public $argv; // pro kazde makro je ulozene jeho poradi (pole)
    public $body;
    public $type;
    public $del;

    function __construct($argc, $argv, $body, $type = MACROS::normal, $del = TRUE) { 

      $this->argc = $argc; 
      $this->argv = $argv; // pole argumentu obshujici pole indexu argumentu v body 
      $this->body = $body;
      $this->type = $type;
      $this->del= $del;
    }
    
    /**
       Expanduje makro se zadanymi argumenty
       @param $readArg pole nactenych argumentu
       @return Expandovany retezec
     */
    public function expand($readArg) {

      $expanded = NULL;
      for ($i = 0; $i < mb_strlen($this->body); $i++) {
        if (isset($readArg[$i])) // na tomto miste ma byt makro
          $expanded .= $readArg[$i];
        else
          $expanded .= mb_substr($this->body, $i, 1);
      }

      if (isset($readArg[$i])) // existuje makro na konci retezce?
        $expanded .= $readArg[$i];
        
      return $expanded;
    }
  }

  /** Objekt samotneho makroprocesoru  */
  class Jmp {
   
    private $input = STDIN;
    private $output = STDOUT;
    private $pos = 0; //index do pole cmd
    private $cmd = NULL;
    private $r = FALSE; // je-li TRUE, redefinice jiz definovaneho makra zpusobi chybu
    private $macros; // pole 
    private $inputSpaces = TRUE; // zpracovavat bile znaky i mimo blok? 
    
    function __construct() { // vytvorit pocatecni makra

      $this->macros["null"] = new Macro("0", NULL, "", MACROS::nul, TRUE);
      $this->macros["__def__"] = new Macro("3", array (0 => "", 1 => "", 2 => ""), "", MACROS::def, FALSE);
      $this->macros["def"] = new Macro("3", array (0 => "", 1 => "", 2 => ""), "", MACROS::def, TRUE);
      $this->macros["__let__"] = new Macro("2", array (0 => "", 1 => ""), "", MACROS::let, FALSE);
      $this->macros["let"] = new Macro("2", array (0 => "", 1 => ""), "", MACROS::let, TRUE);
      $this->macros["__set__"] = new Macro("1", array (0 => ""), "", MACROS::set, FALSE);
      $this->macros["set"] = new Macro("1", array (0 => ""), "", MACROS::set, TRUE);

    }

    /**
       Cte jeden znak ze vstupu / z cmd
       @param $c Vraci se v nem nacteny znak
       @param $spaceAlways Maji-li se nacitat bile znaky i v pripade $inputSpaces == TRUE
     */
    private function read(&$c, $spacesAlways = FALSE) {
       
      do {
        if ($this->pos >= mb_strlen($this->cmd)) {
         
          if (!($line = fgets($this->input))) // konec souboru
            return FALSE;
          
          $this->cmd .= $line;
        
        }
        
        $c = mb_substr($this->cmd, $this->pos++, 1);

      } while(!$this->inputSpaces && !$spacesAlways && mb_ereg_match("\s", $c));

      return TRUE;
    }


    /**
       Zapise retezec na vystup
       @param $string Zapisovany retezec
     */
    private function write($string) {
      fwrite($this->output, $string);
    }

    /**
       Zapise retezec/znak na aktualne zpracovavanou pozici vstupu
       @param $string Zapisovany retezec
     */
    public function toInput($string) {// vlozi retezec na aktualne ctene misto a zbytek odsune
    // zapsat na pozici pos 
      $this->cmd = mb_substr($this->cmd, 0, $this->pos).$string.mb_substr($this->cmd, $this->pos); 
    }


    /**
       Otevre vstupni soubor 
       @param $name Cesta k souboru
     */
    public function openInputFile($name) {
      
      return ($this->input = fopen($name, "r"));
    }

    /**
       Otevre vystupni soubor
       @param $name Cesta k souboru
     */
    public function openOutputFile($name) {
      
      return ($this->output = fopen($name, "w"));
    }
    
    /**
       Nastaveni paramatru -r
     */
    public function setR() {

      $this->r = TRUE;
    }

    /**
       Cte blok az po paritni }. Ocekava, ze vstupni { jiz byla prectena 
       @param $block Vraci se v nem nacteny retezec
       @param $def Pri $def==TRUE neni bran zretel na escape sekvence
     */
    private function readBlock(&$block, $def = FALSE) { 
    
      $blockNum = 0; // kontrola zavorek
      $block = NULL; // pro zapis textu bloku
      $blockAt = FALSE; // je-li predchazejici znak @, mozna escape sekvence
      
      while ($this->read($c, TRUE)) { // TRUE - vzdy chceme nacitat bile znaky
              
        if ($blockAt == TRUE) {
                
          $blockAt = FALSE; // zpracovano @

          if ((!$def && $c != '@' && $c != '}' && $c != '{') || $def) { // neni escape sekvence, treba zapsat predchazejici znak @ a nasledne i aktualni
          // v opacnem pripade jen aktualni

            $block .= "@";

          }

          $block .= $c;
              
        }elseif ($c == "@") { // mozna escape sekvence, zjistime nasledujici znak

          $blockAt = TRUE;
              
        }else {
              
          if ($c == "{") {

            $blockNum++;

          }elseif ($c == "}") {

            if ($blockNum == 0) { // konec bloku, v $block je vysledek, koncova zavorka smazana

              return TRUE;

            }

            $blockNum--;

          }
            
          $block .= $c;
              
        }
      }

      if ($blockNum != 0) { // nespravny pocet uzaviracich/oteviracich slozenych zavorek, konec vstupu
        
        return FALSE;

      }
 
    }

    /**
       Cte nazev makra ci escape sekvenci
       @param $string Vraci se v nem nacteny retezec
     */
    private function readAt(&$string) { // cte nazev makra ci escape sekvenci, vraci ve string
      
      $string = NULL; 

      if (!$this->read($c, TRUE)) // konec vstupu?
        return FALSE;
          
      if (mb_ereg_match('[a-zA-Z_]', $c)) { // makro
           
        $string = $c;

        while ($this->read($c, TRUE)) { // bile znaky chci vzdy - slouzi jako oddelovace
         if (mb_ereg_match('[0-9a-zA-Z_]', $c)) {
            $string .= $c;
          
          } else {

            $this->toInput($c); // vrati navic precteny znak na aktualne cteny vstup
            return TRUE; // vraci nazev makra

          }
        }

        return TRUE; // konec vstupu, nazev makra korektni

      }elseif ($c == "@" || $c == "{" || $c == "}" || $c == '$') { // je escape sekvenci
        
        $string = $c;
        return FALSE; // vraci znak z escape sekvence 
          
      }else { // jine znaky nejsou povoleny
        
        return FALSE;
              
      }
    } 

    /** Cinnost makroprocesoru */
    public function run() {
    
      $macro = NULL; // bude ukazovat na aktualne zpracovavane makro z tabulky, pokud nalezeno
      while ($this->read($c)) {

        if ($c == "@") { // makro nebo escape sekvence

          if ($this->readAt($string)) { // nalezen nazev makra, ulozen ve $string
 
            if (!isset($this->macros[$string])) // makro neexistuje
              exit(ERRORS::semantics);
            
            // makro existuje, pracuj s nim:
            $macro = $this->macros[$string];

            if ($macro->type == MACROS::normal) { // obycejne makro
             
              $readArg = NULL; // pro nactene argumenty, key je pozice v Macro->body
              $count = 0; // pocet prectenych argumentu
              while ($count < $macro->argc) { //nepovede-li se nacist, exit
                if (!$this->read($c)) // konec vstupu
                  exit(ERRORS::semantics);
                
                if ($c == "{") { // nacti blok
                  
                  if (!$this->readBlock($block)) // chyba pri nacitani bloku
                    exit(ERRORS::syntax);
                  
                  // blok nacten, argument zpracovan:
                  $write = $block;

                }else if ($c == "@") { // nacti nazev makra
                
                  if ($this->readAt($string)) // nazev makra nacten 
                    $write = '@'.$string;
                  elseif(isset($string))
                    $write = $string;
                  else // neni nazvem makra, zapis jen jako znak @
                    $write = '@';

                }else { // argumentem je nacteny znak
                  $write = $c;
                }
              
                // nyni prirad indexum parametru v tele makra hodnoty nactenych argumentu:
                $j = 0;
                while (isset($macro->argv[$count][$j])) { // kvuli vyskytu argumentu v tele vicekrat
                  // klic v $readArg je index v body makra
                  $readArg[$macro->argv[$count][$j]] = $write;
                  $j++;

                }

                $count++;
              }
              $this->toInput($macro->expand($readArg)); // expandovani a zapis na vstup
              

            }
              
            elseif ($macro->type == MACROS::nul) { // makro @null | expanduje se jako prazdny retezec

              continue; // novy pruchod while

            }elseif ($macro->type == MACROS::def) { // makro @def
            
              if (!$this->read($c)) // konec vstupu
                exit(ERRORS::semantics);

              if ($c != "@" || !$this->readAt($macroName)) // nenalezen nazev makra
                exit(ERRORS::syntax);

              if (isset($this->macros[$macroName])) { // makro se zadanym nazvem jiz existuje

                if ($this->r || !$this->macros[$macroName]->del) //redefinice je zakazana
                  exit(ERRORS::redef);

              if ($macroName != "null")  // pokus o predefinovani @null je ignorovan
                unset($this->macros[$macroName]); // lze smazat, smaz

              }
                
                
              if (!$this->read($c)) // konec vstupu
                exit(ERRORS::semantics);
              
              if ($c != "{" || !$this->readBlock($macroArg)) { // chyba pri nacitani bloku
                  
                exit(ERRORS::semantics);

              }

                // blok nacten, separuj parametry
              if (!mb_ereg_match('(^(\$[a-zA-Z_][0-9a-zA-Z_]*)(\s*\$[a-zA-Z_][0-9a-zA-Z_]*)*$|^$)', $macroArg)) // spatny format
                exit(ERRORS::syntax); 
               
              // format vyhovuje, nacti argumenty do $args, do $argc pujde jejich pocet:
              mb_ereg_search_init($macroArg, '\$[a-zA-Z_][0-9a-zA-Z_]*');
              
              $argc = 0;
              $args = NULL;
              while (isset($macroArg) && $newArg = mb_ereg_search_regs()) { // nacteni vsech argumentu
                
                $k = 0;
                while (isset($args[$k])) { // kontrola, zda se argument neopakuje
                
                  if ($args[$k] == $newArg[0])
                    exit(ERRORS::semantics);
                  $k++; 
                }

                $args[] = $newArg[0];
                $argc++;

              }

              // nacti telo makra
              if (!$this->read($c)) // konec vstupu
                exit(ERRORS::semantics);

              if ($c != "{" || !$this->readBlock($macroBody, TRUE)) // chyba pri nacitani bloku
                exit(ERRORS::semantics);
                
              // blok nacten, vyhledej v nem argumenty, prirad a smaz z tela makra
              mb_ereg_search_init($macroBody, '\$[a-zA-Z_][0-9a-zA-Z_]*');
              
              $argv = NULL;

              while (isset($macroBody) && $argPosition = mb_ereg_search_pos()) {
                // prochazi se cely blok a hledaji se vyskyty potencialnich argumentu
                if ($argPosition != 0 && (mb_substr($macroBody, $argPosition[0] - 1 , 1) == '@')) {
                  //jedna se o escape sekvenci
                  //smaz predchozi znak @ a znak $ ber jako obycejny

                  $macroBody = mb_substr($macroBody, 0, $argPosition[0] - 1).mb_substr($macroBody, $argPosition[0]);

                // inicializace kvuli presnosti indexu
                mb_ereg_search_init($macroBody, '\$[a-zA-Z_][0-9a-zA-Z_]*');
                mb_ereg_search_setpos($argPosition[0]);

                }else {

                  $argBody = mb_substr($macroBody, $argPosition[0], $argPosition[1]); // nazev argumentu
                  for ($i = 0; $i < $argc; $i++) { // porovnavani s deklarovanymi argumenty 
                    if (preg_quote($args[$i]) == preg_quote($argBody)) {
                      
                      $argv[$i][] = $argPosition[0]; // index, kam se ma makro expandovat
                      // odstran z tela makra tento argument:
                      $macroBody = mb_substr($macroBody, 0, $argPosition[0]).'X'.mb_substr($macroBody, $argPosition[0] + mb_strlen($argBody)); // makro nahrazeno 'X'

                      // inicializace kvuli presnosti indexu
                      mb_ereg_search_init($macroBody, '\$[a-zA-Z_][0-9a-zA-Z_]*');
                      mb_ereg_search_setpos($argPosition[0]);
                      break;
                    
                    } 
                  }
                }
              }
              
              //vyhledej zbytek escape sekvenci:
              mb_ereg_search_init($macroBody, '@\$[^a-zA-Z_]|@\$$');
              $deleted = 0;
              while (isset($macroBody) && $escapePosition = mb_ereg_search_pos()) {
                $macroBody = mb_substr($macroBody, 0, $escapePosition[0]).mb_substr($macroBody, $escapePosition[0] + 1);
                // prepocitani indexu
                for ($i = 0; $i < $argc; $i++) {

                  $j = 0;
                  while (isset($argv[$i][$j])) {
                    
                    if (($argv[$i][$j] + $deleted) > $escapePosition[0])
                      $argv[$i][$j]--;
                    
                    $j++;

                  }
                }
                
                $deleted++;
              }
              
              if ($macroName != "null") {  // pokus o predefinovani @null je ignorovan
                
                // vse v poradku, vytvor makro a zapis do tabulky maker:
                $this->macros[$macroName] = new Macro($argc, $argv, $macroBody);
              }

            }elseif ($macro->type == MACROS::let) { // makro @let, tvar: @let@a@b, priradi makru @a makro @b


              if (!$this->read($c)) // konec vstupu
                exit(ERRORS::semantics);

              if ($c != "@" || !$this->readAt($macroA)) // nenacten nazev makra
                exit(ERRORS::syntax);
              
              if (!$this->read($c)) // konec vstupu
                exit(ERRORS::semantics);

              if ($c != "@" || !$this->readAt($macroB)) // nenacten nazev makra
                exit(ERRORS::syntax);

              if ($macroA != "null") { // pokus o predefinovani @null je ignorovan

                if ($macroB == "null") { // mazani makra
                  
                  if (isset($this->macros[$macroA])) { // makro se zadanym nazvem existuje

                    if (!$this->macros[$macroA]->del) // toto makro nelze smazat
                      exit(ERRORS::redef);
                      
                    unset($this->macros[$macroA]); // lze smazat, smaz

                  }
                }elseif(!isset($this->macros[$macroB])) { // definujici makro neexistuje, chyba
                
                  exit(ERRORS::semantics);

                }else{ // prirad synonymum, pokud je to mozne
                
                  if (isset($this->macros[$macroA])) { // definovane makro existuje

                    if ($this->r || !$this->macros[$macroA]->del) //redefinice je zakazana
                      exit(ERRORS::redef);

                    unset($this->macros[$macroA]); // lze smazat, smaz
                  
                  }

                  $this->macros[$macroA] = $this->macros[$macroB]; // vytvoreni synonyma

                }
              }
            
            }elseif ($macro->type == MACROS::set) { // makro @set
              // nacti blok, ktery ma obsahovat "-INPUT_SPACES" nebo "+INPUT_SPACES"
              if (!$this->read($c)) // konec vstupu
                exit(ERRORS::semantics);

              if ($c != "{" || !$this->readBlock($block)) // chyba pri nacitani bloku
                exit(ERRORS::syntax);

              if ($block == "-INPUT_SPACES")
                $this->inputSpaces = FALSE;
              elseif ($block == "+INPUT_SPACES")
                $this->inputSpaces = TRUE;
              else
                exit(ERRORS::semantics);
            }

          }elseif (isset($string)) { // escape sekvence (readAt vratila FALSE, ve string neni nazev makra, ale je platnou escape sekvenci)
          
            $this->write($string); // hned na vystup
          
          }else // jine znaky nejsou povoleny (neplatny znak po znaku @)
            exit(ERRORS::syntax);

        }elseif ($c == "{") { // blok - nacti a vypis

          if (!$this->readBlock($string)) // chyba pri nacitani bloku
            exit(ERRORS::syntax);

          $this->write($string);

        }elseif ($c == "}" || $c == '$') { // nepovoleny vstup

          exit(ERRORS::syntax);
              
        }else { // jiny znak, hned na vystup
          
          $this->write($c);

        }
      }
    }
  }

//////////////////////////PROGRAM////////////////////////

  $shortopts = "";
  $shortopts .= "r";
  
  $longopts = array( 
    "help",
    "input:",
    "output:",
    "cmd:",
  );

  $options = getopt($shortopts, $longopts);
  
  if (isset($options["help"])) { // help samostatne

    if ($argc == 2)
      echo "Jednoduchy makroprocesor, jenz je zjednodusenou verzi makroprocesoru vestaveneho uvnitr typografickeho systemu TeX.

Parametry:
-- help Napoveda
--input=filename Vstupni textovy soubor se zakladnim ASCII kodovanim
--output=filename Textovy vystupni soubor tez v ASCII kodovani
--cmd=text Text bude pred zacatkem zpracovani vstupu vlozen na zacatek vstupu
-r Redefinice jiz definovaneho makra pomoci makra @def zpusobi chybu s kodem 57\n";
    else
      exit(ERRORS::params);
    
    exit(SUCCESS);
  }

  $jmp = new Jmp();
  $paramCount = 0; // pocet zpracovanych parametru
  
  if (isset($options["input"])) {
    
    $paramCount++;

    if (!$jmp->openInputFile($options["input"]))
      exit(ERRORS::input);
  }

  if (isset($options["output"])) {

    $paramCount++;

    if (!$jmp->openOutputFile($options["output"]))
      exit(ERRORS::output);
  }
  
  if (isset($options["cmd"])) {

    $paramCount++;
    $jmp->toInput($options["cmd"]);
  }

  if (isset($options["r"])) {

    $paramCount++;
    $jmp->setR();
  }

  if ($argc > ($paramCount + 1)) {

    exit(ERRORS::params);
  }

  $jmp->run();
  
  // nebyl-li skript ukoncen, bylo vse uspesne zpracovano, vrat SUCCESS
  return SUCCESS;
?>
