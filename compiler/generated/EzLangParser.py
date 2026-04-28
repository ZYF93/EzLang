# Generated from grammar/EzLang.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,75,782,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,2,22,7,22,2,23,7,23,2,24,7,24,2,25,7,25,2,26,7,26,
        2,27,7,27,2,28,7,28,2,29,7,29,2,30,7,30,2,31,7,31,2,32,7,32,2,33,
        7,33,2,34,7,34,2,35,7,35,2,36,7,36,2,37,7,37,2,38,7,38,2,39,7,39,
        2,40,7,40,2,41,7,41,2,42,7,42,2,43,7,43,2,44,7,44,2,45,7,45,2,46,
        7,46,2,47,7,47,2,48,7,48,2,49,7,49,2,50,7,50,2,51,7,51,2,52,7,52,
        2,53,7,53,2,54,7,54,2,55,7,55,2,56,7,56,2,57,7,57,2,58,7,58,2,59,
        7,59,2,60,7,60,2,61,7,61,2,62,7,62,2,63,7,63,1,0,5,0,130,8,0,10,
        0,12,0,133,9,0,1,0,1,0,1,1,1,1,1,2,1,2,1,2,1,2,1,2,1,2,1,2,1,2,1,
        2,1,2,1,2,1,2,1,2,3,2,152,8,2,1,3,3,3,155,8,3,1,3,1,3,1,3,1,3,3,
        3,161,8,3,1,3,1,3,1,3,1,3,1,4,3,4,168,8,4,1,4,3,4,171,8,4,1,4,1,
        4,1,4,1,4,3,4,177,8,4,1,4,1,4,1,4,1,4,1,5,1,5,1,5,1,5,3,5,187,8,
        5,1,5,1,5,1,5,1,5,1,6,1,6,1,6,3,6,196,8,6,1,6,1,6,5,6,200,8,6,10,
        6,12,6,203,9,6,1,6,1,6,3,6,207,8,6,1,7,1,7,1,7,1,7,1,7,1,7,1,7,1,
        7,3,7,217,8,7,1,7,1,7,1,7,1,7,1,7,1,7,1,7,3,7,226,8,7,1,8,1,8,1,
        8,3,8,231,8,8,1,8,1,8,1,8,3,8,236,8,8,1,8,1,8,1,8,3,8,241,8,8,1,
        8,1,8,1,8,3,8,246,8,8,3,8,248,8,8,1,9,1,9,5,9,252,8,9,10,9,12,9,
        255,9,9,1,9,1,9,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,1,10,
        1,10,3,10,270,8,10,1,10,1,10,1,10,1,10,1,10,3,10,277,8,10,1,11,1,
        11,1,11,1,11,1,11,1,11,1,11,1,12,1,12,1,12,1,12,1,12,1,12,1,12,5,
        12,293,8,12,10,12,12,12,296,9,12,1,12,1,12,3,12,300,8,12,1,13,1,
        13,1,13,3,13,305,8,13,1,14,1,14,1,14,1,14,1,14,1,14,3,14,313,8,14,
        1,15,1,15,3,15,317,8,15,1,15,1,15,1,16,1,16,1,16,1,16,1,17,1,17,
        3,17,327,8,17,1,18,1,18,3,18,331,8,18,1,19,1,19,1,19,1,20,1,20,1,
        20,1,21,1,21,1,22,1,22,1,22,1,22,1,22,3,22,346,8,22,1,23,1,23,1,
        24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,
        24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,
        24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,1,24,3,24,385,8,24,1,25,1,
        25,1,25,1,25,1,25,3,25,392,8,25,1,25,5,25,395,8,25,10,25,12,25,398,
        9,25,1,26,1,26,1,26,5,26,403,8,26,10,26,12,26,406,9,26,1,27,1,27,
        1,27,5,27,411,8,27,10,27,12,27,414,9,27,1,28,1,28,1,28,5,28,419,
        8,28,10,28,12,28,422,9,28,1,29,1,29,1,29,5,29,427,8,29,10,29,12,
        29,430,9,29,1,30,1,30,1,30,5,30,435,8,30,10,30,12,30,438,9,30,1,
        31,1,31,1,31,5,31,443,8,31,10,31,12,31,446,9,31,1,32,1,32,1,32,5,
        32,451,8,32,10,32,12,32,454,9,32,1,33,1,33,1,33,5,33,459,8,33,10,
        33,12,33,462,9,33,1,34,1,34,1,34,5,34,467,8,34,10,34,12,34,470,9,
        34,1,35,1,35,1,35,5,35,475,8,35,10,35,12,35,478,9,35,1,36,1,36,1,
        36,1,36,1,36,3,36,485,8,36,1,37,1,37,5,37,489,8,37,10,37,12,37,492,
        9,37,1,38,1,38,1,38,1,38,3,38,498,8,38,1,38,1,38,1,38,1,38,1,38,
        3,38,505,8,38,1,39,1,39,1,39,1,39,1,39,1,39,3,39,513,8,39,1,39,1,
        39,1,39,1,39,1,39,1,39,1,39,1,39,1,39,1,39,1,39,1,39,1,39,1,39,1,
        39,3,39,530,8,39,1,40,3,40,533,8,40,1,40,1,40,3,40,537,8,40,1,40,
        1,40,1,40,3,40,542,8,40,1,40,1,40,1,40,3,40,547,8,40,1,40,1,40,3,
        40,551,8,40,1,40,1,40,1,40,3,40,556,8,40,1,40,1,40,3,40,560,8,40,
        1,41,1,41,1,41,5,41,565,8,41,10,41,12,41,568,9,41,1,42,1,42,1,42,
        1,42,1,42,3,42,575,8,42,1,43,1,43,1,43,5,43,580,8,43,10,43,12,43,
        583,9,43,1,44,1,44,1,44,1,44,1,44,1,44,1,44,1,44,3,44,593,8,44,1,
        45,1,45,5,45,597,8,45,10,45,12,45,600,9,45,1,45,1,45,1,46,1,46,1,
        46,1,46,1,46,5,46,609,8,46,10,46,12,46,612,9,46,1,46,3,46,615,8,
        46,1,46,1,46,1,47,1,47,1,47,1,47,1,47,1,47,1,47,1,47,1,47,1,47,1,
        47,1,47,3,47,631,8,47,1,48,1,48,1,48,1,48,1,48,1,48,1,48,1,48,1,
        48,1,48,3,48,643,8,48,1,49,1,49,1,49,1,50,1,50,1,50,1,50,5,50,652,
        8,50,10,50,12,50,655,9,50,3,50,657,8,50,1,50,1,50,1,51,1,51,1,51,
        1,51,1,51,5,51,666,8,51,10,51,12,51,669,9,51,1,51,1,51,1,52,1,52,
        1,52,1,52,5,52,677,8,52,10,52,12,52,680,9,52,1,52,3,52,683,8,52,
        1,52,1,52,1,53,1,53,1,53,1,53,1,53,1,53,1,53,1,53,1,53,3,53,696,
        8,53,1,54,1,54,1,54,1,55,1,55,1,56,1,56,1,56,5,56,706,8,56,10,56,
        12,56,709,9,56,1,57,1,57,1,57,1,57,3,57,715,8,57,1,58,1,58,1,58,
        1,58,1,58,3,58,722,8,58,1,59,1,59,3,59,726,8,59,1,59,1,59,1,59,1,
        59,1,59,1,59,1,59,1,59,1,59,1,59,3,59,738,8,59,1,59,1,59,1,59,1,
        59,1,59,1,59,3,59,746,8,59,1,60,1,60,1,60,5,60,751,8,60,10,60,12,
        60,754,9,60,1,61,1,61,1,61,1,61,1,62,1,62,1,62,1,62,5,62,764,8,62,
        10,62,12,62,767,9,62,1,62,1,62,1,63,1,63,1,63,1,63,5,63,775,8,63,
        10,63,12,63,778,9,63,1,63,1,63,1,63,0,0,64,0,2,4,6,8,10,12,14,16,
        18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48,50,52,54,56,58,60,
        62,64,66,68,70,72,74,76,78,80,82,84,86,88,90,92,94,96,98,100,102,
        104,106,108,110,112,114,116,118,120,122,124,126,0,6,2,0,27,36,47,
        47,1,0,39,40,2,0,41,42,45,46,1,0,37,38,1,0,48,49,1,0,50,52,836,0,
        131,1,0,0,0,2,136,1,0,0,0,4,151,1,0,0,0,6,154,1,0,0,0,8,167,1,0,
        0,0,10,182,1,0,0,0,12,192,1,0,0,0,14,225,1,0,0,0,16,247,1,0,0,0,
        18,249,1,0,0,0,20,276,1,0,0,0,22,278,1,0,0,0,24,285,1,0,0,0,26,301,
        1,0,0,0,28,312,1,0,0,0,30,314,1,0,0,0,32,320,1,0,0,0,34,324,1,0,
        0,0,36,328,1,0,0,0,38,332,1,0,0,0,40,335,1,0,0,0,42,338,1,0,0,0,
        44,345,1,0,0,0,46,347,1,0,0,0,48,384,1,0,0,0,50,386,1,0,0,0,52,399,
        1,0,0,0,54,407,1,0,0,0,56,415,1,0,0,0,58,423,1,0,0,0,60,431,1,0,
        0,0,62,439,1,0,0,0,64,447,1,0,0,0,66,455,1,0,0,0,68,463,1,0,0,0,
        70,471,1,0,0,0,72,484,1,0,0,0,74,486,1,0,0,0,76,504,1,0,0,0,78,529,
        1,0,0,0,80,559,1,0,0,0,82,561,1,0,0,0,84,569,1,0,0,0,86,576,1,0,
        0,0,88,592,1,0,0,0,90,594,1,0,0,0,92,603,1,0,0,0,94,630,1,0,0,0,
        96,642,1,0,0,0,98,644,1,0,0,0,100,647,1,0,0,0,102,660,1,0,0,0,104,
        672,1,0,0,0,106,695,1,0,0,0,108,697,1,0,0,0,110,700,1,0,0,0,112,
        702,1,0,0,0,114,714,1,0,0,0,116,721,1,0,0,0,118,745,1,0,0,0,120,
        747,1,0,0,0,122,755,1,0,0,0,124,759,1,0,0,0,126,770,1,0,0,0,128,
        130,3,2,1,0,129,128,1,0,0,0,130,133,1,0,0,0,131,129,1,0,0,0,131,
        132,1,0,0,0,132,134,1,0,0,0,133,131,1,0,0,0,134,135,5,0,0,1,135,
        1,1,0,0,0,136,137,3,4,2,0,137,3,1,0,0,0,138,152,3,6,3,0,139,152,
        3,8,4,0,140,152,3,10,5,0,141,152,3,12,6,0,142,152,3,16,8,0,143,152,
        3,22,11,0,144,152,3,24,12,0,145,152,3,28,14,0,146,152,3,30,15,0,
        147,152,3,32,16,0,148,152,3,34,17,0,149,152,3,36,18,0,150,152,3,
        38,19,0,151,138,1,0,0,0,151,139,1,0,0,0,151,140,1,0,0,0,151,141,
        1,0,0,0,151,142,1,0,0,0,151,143,1,0,0,0,151,144,1,0,0,0,151,145,
        1,0,0,0,151,146,1,0,0,0,151,147,1,0,0,0,151,148,1,0,0,0,151,149,
        1,0,0,0,151,150,1,0,0,0,152,5,1,0,0,0,153,155,3,40,20,0,154,153,
        1,0,0,0,154,155,1,0,0,0,155,156,1,0,0,0,156,157,5,1,0,0,157,160,
        5,69,0,0,158,159,5,58,0,0,159,161,3,110,55,0,160,158,1,0,0,0,160,
        161,1,0,0,0,161,162,1,0,0,0,162,163,5,47,0,0,163,164,3,42,21,0,164,
        165,5,59,0,0,165,7,1,0,0,0,166,168,3,40,20,0,167,166,1,0,0,0,167,
        168,1,0,0,0,168,170,1,0,0,0,169,171,5,9,0,0,170,169,1,0,0,0,170,
        171,1,0,0,0,171,172,1,0,0,0,172,173,5,2,0,0,173,176,5,69,0,0,174,
        175,5,58,0,0,175,177,3,110,55,0,176,174,1,0,0,0,176,177,1,0,0,0,
        177,178,1,0,0,0,178,179,5,47,0,0,179,180,3,42,21,0,180,181,5,59,
        0,0,181,9,1,0,0,0,182,183,5,3,0,0,183,186,5,69,0,0,184,185,5,58,
        0,0,185,187,3,110,55,0,186,184,1,0,0,0,186,187,1,0,0,0,187,188,1,
        0,0,0,188,189,5,47,0,0,189,190,3,42,21,0,190,191,5,59,0,0,191,11,
        1,0,0,0,192,193,5,4,0,0,193,195,5,69,0,0,194,196,3,124,62,0,195,
        194,1,0,0,0,195,196,1,0,0,0,196,197,1,0,0,0,197,201,5,65,0,0,198,
        200,3,14,7,0,199,198,1,0,0,0,200,203,1,0,0,0,201,199,1,0,0,0,201,
        202,1,0,0,0,202,204,1,0,0,0,203,201,1,0,0,0,204,206,5,66,0,0,205,
        207,5,59,0,0,206,205,1,0,0,0,206,207,1,0,0,0,207,13,1,0,0,0,208,
        209,5,26,0,0,209,210,5,69,0,0,210,226,5,59,0,0,211,212,5,69,0,0,
        212,213,5,58,0,0,213,216,3,110,55,0,214,215,5,47,0,0,215,217,3,42,
        21,0,216,214,1,0,0,0,216,217,1,0,0,0,217,218,1,0,0,0,218,219,5,59,
        0,0,219,226,1,0,0,0,220,221,5,69,0,0,221,222,5,47,0,0,222,223,3,
        42,21,0,223,224,5,59,0,0,224,226,1,0,0,0,225,208,1,0,0,0,225,211,
        1,0,0,0,225,220,1,0,0,0,226,15,1,0,0,0,227,228,5,5,0,0,228,230,5,
        69,0,0,229,231,3,124,62,0,230,229,1,0,0,0,230,231,1,0,0,0,231,232,
        1,0,0,0,232,233,5,47,0,0,233,235,3,18,9,0,234,236,5,59,0,0,235,234,
        1,0,0,0,235,236,1,0,0,0,236,248,1,0,0,0,237,238,5,5,0,0,238,240,
        5,69,0,0,239,241,3,124,62,0,240,239,1,0,0,0,240,241,1,0,0,0,241,
        242,1,0,0,0,242,243,5,47,0,0,243,245,3,110,55,0,244,246,5,59,0,0,
        245,244,1,0,0,0,245,246,1,0,0,0,246,248,1,0,0,0,247,227,1,0,0,0,
        247,237,1,0,0,0,248,17,1,0,0,0,249,253,5,65,0,0,250,252,3,20,10,
        0,251,250,1,0,0,0,252,255,1,0,0,0,253,251,1,0,0,0,253,254,1,0,0,
        0,254,256,1,0,0,0,255,253,1,0,0,0,256,257,5,66,0,0,257,19,1,0,0,
        0,258,259,5,26,0,0,259,260,5,69,0,0,260,277,5,59,0,0,261,262,5,67,
        0,0,262,263,5,69,0,0,263,264,5,58,0,0,264,265,3,110,55,0,265,266,
        5,68,0,0,266,267,5,58,0,0,267,269,3,110,55,0,268,270,5,59,0,0,269,
        268,1,0,0,0,269,270,1,0,0,0,270,277,1,0,0,0,271,272,5,69,0,0,272,
        273,5,58,0,0,273,274,3,110,55,0,274,275,5,59,0,0,275,277,1,0,0,0,
        276,258,1,0,0,0,276,261,1,0,0,0,276,271,1,0,0,0,277,21,1,0,0,0,278,
        279,5,6,0,0,279,280,5,2,0,0,280,281,5,69,0,0,281,282,5,58,0,0,282,
        283,3,110,55,0,283,284,5,59,0,0,284,23,1,0,0,0,285,286,5,14,0,0,
        286,287,5,72,0,0,287,288,5,12,0,0,288,289,5,65,0,0,289,294,3,26,
        13,0,290,291,5,60,0,0,291,293,3,26,13,0,292,290,1,0,0,0,293,296,
        1,0,0,0,294,292,1,0,0,0,294,295,1,0,0,0,295,297,1,0,0,0,296,294,
        1,0,0,0,297,299,5,66,0,0,298,300,5,59,0,0,299,298,1,0,0,0,299,300,
        1,0,0,0,300,25,1,0,0,0,301,304,5,69,0,0,302,303,5,21,0,0,303,305,
        5,69,0,0,304,302,1,0,0,0,304,305,1,0,0,0,305,27,1,0,0,0,306,307,
        5,13,0,0,307,313,3,6,3,0,308,309,5,13,0,0,309,313,3,8,4,0,310,311,
        5,13,0,0,311,313,3,10,5,0,312,306,1,0,0,0,312,308,1,0,0,0,312,310,
        1,0,0,0,313,29,1,0,0,0,314,316,5,19,0,0,315,317,3,42,21,0,316,315,
        1,0,0,0,316,317,1,0,0,0,317,318,1,0,0,0,318,319,5,59,0,0,319,31,
        1,0,0,0,320,321,5,17,0,0,321,322,3,42,21,0,322,323,5,59,0,0,323,
        33,1,0,0,0,324,326,5,10,0,0,325,327,5,59,0,0,326,325,1,0,0,0,326,
        327,1,0,0,0,327,35,1,0,0,0,328,330,5,11,0,0,329,331,5,59,0,0,330,
        329,1,0,0,0,330,331,1,0,0,0,331,37,1,0,0,0,332,333,3,42,21,0,333,
        334,5,59,0,0,334,39,1,0,0,0,335,336,5,62,0,0,336,337,5,69,0,0,337,
        41,1,0,0,0,338,339,3,44,22,0,339,43,1,0,0,0,340,341,3,48,24,0,341,
        342,3,46,23,0,342,343,3,44,22,0,343,346,1,0,0,0,344,346,3,48,24,
        0,345,340,1,0,0,0,345,344,1,0,0,0,346,45,1,0,0,0,347,348,7,0,0,0,
        348,47,1,0,0,0,349,350,3,50,25,0,350,351,5,57,0,0,351,352,3,90,45,
        0,352,353,5,58,0,0,353,354,3,48,24,0,354,385,1,0,0,0,355,356,3,50,
        25,0,356,357,5,57,0,0,357,358,3,90,45,0,358,359,5,58,0,0,359,360,
        3,90,45,0,360,385,1,0,0,0,361,362,3,50,25,0,362,363,5,57,0,0,363,
        364,3,90,45,0,364,385,1,0,0,0,365,366,3,50,25,0,366,367,5,57,0,0,
        367,368,5,10,0,0,368,385,1,0,0,0,369,370,3,50,25,0,370,371,5,57,
        0,0,371,372,5,11,0,0,372,385,1,0,0,0,373,374,3,50,25,0,374,375,5,
        57,0,0,375,376,3,42,21,0,376,377,5,58,0,0,377,378,3,42,21,0,378,
        385,1,0,0,0,379,380,3,50,25,0,380,381,5,57,0,0,381,382,3,42,21,0,
        382,385,1,0,0,0,383,385,3,50,25,0,384,349,1,0,0,0,384,355,1,0,0,
        0,384,361,1,0,0,0,384,365,1,0,0,0,384,369,1,0,0,0,384,373,1,0,0,
        0,384,379,1,0,0,0,384,383,1,0,0,0,385,49,1,0,0,0,386,396,3,52,26,
        0,387,388,5,25,0,0,388,389,5,69,0,0,389,391,5,63,0,0,390,392,3,86,
        43,0,391,390,1,0,0,0,391,392,1,0,0,0,392,393,1,0,0,0,393,395,5,64,
        0,0,394,387,1,0,0,0,395,398,1,0,0,0,396,394,1,0,0,0,396,397,1,0,
        0,0,397,51,1,0,0,0,398,396,1,0,0,0,399,404,3,54,27,0,400,401,5,44,
        0,0,401,403,3,54,27,0,402,400,1,0,0,0,403,406,1,0,0,0,404,402,1,
        0,0,0,404,405,1,0,0,0,405,53,1,0,0,0,406,404,1,0,0,0,407,412,3,56,
        28,0,408,409,5,43,0,0,409,411,3,56,28,0,410,408,1,0,0,0,411,414,
        1,0,0,0,412,410,1,0,0,0,412,413,1,0,0,0,413,55,1,0,0,0,414,412,1,
        0,0,0,415,420,3,58,29,0,416,417,5,54,0,0,417,419,3,58,29,0,418,416,
        1,0,0,0,419,422,1,0,0,0,420,418,1,0,0,0,420,421,1,0,0,0,421,57,1,
        0,0,0,422,420,1,0,0,0,423,428,3,60,30,0,424,425,5,55,0,0,425,427,
        3,60,30,0,426,424,1,0,0,0,427,430,1,0,0,0,428,426,1,0,0,0,428,429,
        1,0,0,0,429,59,1,0,0,0,430,428,1,0,0,0,431,436,3,62,31,0,432,433,
        5,53,0,0,433,435,3,62,31,0,434,432,1,0,0,0,435,438,1,0,0,0,436,434,
        1,0,0,0,436,437,1,0,0,0,437,61,1,0,0,0,438,436,1,0,0,0,439,444,3,
        64,32,0,440,441,7,1,0,0,441,443,3,64,32,0,442,440,1,0,0,0,443,446,
        1,0,0,0,444,442,1,0,0,0,444,445,1,0,0,0,445,63,1,0,0,0,446,444,1,
        0,0,0,447,452,3,66,33,0,448,449,7,2,0,0,449,451,3,66,33,0,450,448,
        1,0,0,0,451,454,1,0,0,0,452,450,1,0,0,0,452,453,1,0,0,0,453,65,1,
        0,0,0,454,452,1,0,0,0,455,460,3,68,34,0,456,457,7,3,0,0,457,459,
        3,68,34,0,458,456,1,0,0,0,459,462,1,0,0,0,460,458,1,0,0,0,460,461,
        1,0,0,0,461,67,1,0,0,0,462,460,1,0,0,0,463,468,3,70,35,0,464,465,
        7,4,0,0,465,467,3,70,35,0,466,464,1,0,0,0,467,470,1,0,0,0,468,466,
        1,0,0,0,468,469,1,0,0,0,469,69,1,0,0,0,470,468,1,0,0,0,471,476,3,
        72,36,0,472,473,7,5,0,0,473,475,3,72,36,0,474,472,1,0,0,0,475,478,
        1,0,0,0,476,474,1,0,0,0,476,477,1,0,0,0,477,71,1,0,0,0,478,476,1,
        0,0,0,479,480,5,56,0,0,480,485,3,72,36,0,481,482,5,49,0,0,482,485,
        3,72,36,0,483,485,3,74,37,0,484,479,1,0,0,0,484,481,1,0,0,0,484,
        483,1,0,0,0,485,73,1,0,0,0,486,490,3,78,39,0,487,489,3,76,38,0,488,
        487,1,0,0,0,489,492,1,0,0,0,490,488,1,0,0,0,490,491,1,0,0,0,491,
        75,1,0,0,0,492,490,1,0,0,0,493,494,5,61,0,0,494,505,5,69,0,0,495,
        497,5,63,0,0,496,498,3,86,43,0,497,496,1,0,0,0,497,498,1,0,0,0,498,
        499,1,0,0,0,499,505,5,64,0,0,500,501,5,67,0,0,501,502,3,42,21,0,
        502,503,5,68,0,0,503,505,1,0,0,0,504,493,1,0,0,0,504,495,1,0,0,0,
        504,500,1,0,0,0,505,77,1,0,0,0,506,530,5,70,0,0,507,530,5,71,0,0,
        508,530,5,72,0,0,509,530,5,23,0,0,510,512,5,69,0,0,511,513,3,126,
        63,0,512,511,1,0,0,0,512,513,1,0,0,0,513,530,1,0,0,0,514,515,5,63,
        0,0,515,516,3,42,21,0,516,517,5,64,0,0,517,530,1,0,0,0,518,530,3,
        90,45,0,519,530,3,80,40,0,520,530,3,92,46,0,521,530,3,96,48,0,522,
        530,3,98,49,0,523,530,3,100,50,0,524,530,3,102,51,0,525,530,3,104,
        52,0,526,530,3,108,54,0,527,528,5,8,0,0,528,530,3,42,21,0,529,506,
        1,0,0,0,529,507,1,0,0,0,529,508,1,0,0,0,529,509,1,0,0,0,529,510,
        1,0,0,0,529,514,1,0,0,0,529,518,1,0,0,0,529,519,1,0,0,0,529,520,
        1,0,0,0,529,521,1,0,0,0,529,522,1,0,0,0,529,523,1,0,0,0,529,524,
        1,0,0,0,529,525,1,0,0,0,529,526,1,0,0,0,529,527,1,0,0,0,530,79,1,
        0,0,0,531,533,3,124,62,0,532,531,1,0,0,0,532,533,1,0,0,0,533,534,
        1,0,0,0,534,536,5,63,0,0,535,537,3,82,41,0,536,535,1,0,0,0,536,537,
        1,0,0,0,537,538,1,0,0,0,538,541,5,64,0,0,539,540,5,58,0,0,540,542,
        3,110,55,0,541,539,1,0,0,0,541,542,1,0,0,0,542,543,1,0,0,0,543,544,
        5,24,0,0,544,560,3,42,21,0,545,547,3,124,62,0,546,545,1,0,0,0,546,
        547,1,0,0,0,547,548,1,0,0,0,548,550,5,63,0,0,549,551,3,82,41,0,550,
        549,1,0,0,0,550,551,1,0,0,0,551,552,1,0,0,0,552,555,5,64,0,0,553,
        554,5,58,0,0,554,556,3,110,55,0,555,553,1,0,0,0,555,556,1,0,0,0,
        556,557,1,0,0,0,557,558,5,24,0,0,558,560,3,90,45,0,559,532,1,0,0,
        0,559,546,1,0,0,0,560,81,1,0,0,0,561,566,3,84,42,0,562,563,5,60,
        0,0,563,565,3,84,42,0,564,562,1,0,0,0,565,568,1,0,0,0,566,564,1,
        0,0,0,566,567,1,0,0,0,567,83,1,0,0,0,568,566,1,0,0,0,569,570,5,69,
        0,0,570,571,5,58,0,0,571,574,3,110,55,0,572,573,5,47,0,0,573,575,
        3,42,21,0,574,572,1,0,0,0,574,575,1,0,0,0,575,85,1,0,0,0,576,581,
        3,88,44,0,577,578,5,60,0,0,578,580,3,88,44,0,579,577,1,0,0,0,580,
        583,1,0,0,0,581,579,1,0,0,0,581,582,1,0,0,0,582,87,1,0,0,0,583,581,
        1,0,0,0,584,585,5,69,0,0,585,586,5,47,0,0,586,593,3,42,21,0,587,
        588,5,69,0,0,588,589,5,47,0,0,589,593,5,57,0,0,590,591,5,26,0,0,
        591,593,3,42,21,0,592,584,1,0,0,0,592,587,1,0,0,0,592,590,1,0,0,
        0,593,89,1,0,0,0,594,598,5,65,0,0,595,597,3,4,2,0,596,595,1,0,0,
        0,597,600,1,0,0,0,598,596,1,0,0,0,598,599,1,0,0,0,599,601,1,0,0,
        0,600,598,1,0,0,0,601,602,5,66,0,0,602,91,1,0,0,0,603,604,5,15,0,
        0,604,605,5,65,0,0,605,610,3,94,47,0,606,607,5,60,0,0,607,609,3,
        94,47,0,608,606,1,0,0,0,609,612,1,0,0,0,610,608,1,0,0,0,610,611,
        1,0,0,0,611,614,1,0,0,0,612,610,1,0,0,0,613,615,5,60,0,0,614,613,
        1,0,0,0,614,615,1,0,0,0,615,616,1,0,0,0,616,617,5,66,0,0,617,93,
        1,0,0,0,618,619,5,63,0,0,619,620,3,42,21,0,620,621,5,64,0,0,621,
        622,5,57,0,0,622,623,3,90,45,0,623,631,1,0,0,0,624,625,5,63,0,0,
        625,626,3,42,21,0,626,627,5,64,0,0,627,628,5,57,0,0,628,629,3,42,
        21,0,629,631,1,0,0,0,630,618,1,0,0,0,630,624,1,0,0,0,631,95,1,0,
        0,0,632,633,5,7,0,0,633,634,5,69,0,0,634,635,5,20,0,0,635,636,3,
        42,21,0,636,637,5,26,0,0,637,638,3,42,21,0,638,639,3,90,45,0,639,
        643,1,0,0,0,640,641,5,7,0,0,641,643,3,90,45,0,642,632,1,0,0,0,642,
        640,1,0,0,0,643,97,1,0,0,0,644,645,5,16,0,0,645,646,3,90,45,0,646,
        99,1,0,0,0,647,656,5,67,0,0,648,653,3,42,21,0,649,650,5,60,0,0,650,
        652,3,42,21,0,651,649,1,0,0,0,652,655,1,0,0,0,653,651,1,0,0,0,653,
        654,1,0,0,0,654,657,1,0,0,0,655,653,1,0,0,0,656,648,1,0,0,0,656,
        657,1,0,0,0,657,658,1,0,0,0,658,659,5,68,0,0,659,101,1,0,0,0,660,
        661,5,22,0,0,661,662,5,67,0,0,662,667,3,42,21,0,663,664,5,60,0,0,
        664,666,3,42,21,0,665,663,1,0,0,0,666,669,1,0,0,0,667,665,1,0,0,
        0,667,668,1,0,0,0,668,670,1,0,0,0,669,667,1,0,0,0,670,671,5,68,0,
        0,671,103,1,0,0,0,672,673,5,65,0,0,673,678,3,106,53,0,674,675,5,
        60,0,0,675,677,3,106,53,0,676,674,1,0,0,0,677,680,1,0,0,0,678,676,
        1,0,0,0,678,679,1,0,0,0,679,682,1,0,0,0,680,678,1,0,0,0,681,683,
        5,60,0,0,682,681,1,0,0,0,682,683,1,0,0,0,683,684,1,0,0,0,684,685,
        5,66,0,0,685,105,1,0,0,0,686,687,5,69,0,0,687,688,5,58,0,0,688,689,
        3,110,55,0,689,690,5,47,0,0,690,691,3,42,21,0,691,696,1,0,0,0,692,
        693,5,69,0,0,693,694,5,47,0,0,694,696,3,42,21,0,695,686,1,0,0,0,
        695,692,1,0,0,0,696,107,1,0,0,0,697,698,5,18,0,0,698,699,3,42,21,
        0,699,109,1,0,0,0,700,701,3,112,56,0,701,111,1,0,0,0,702,707,3,114,
        57,0,703,704,5,54,0,0,704,706,3,114,57,0,705,703,1,0,0,0,706,709,
        1,0,0,0,707,705,1,0,0,0,707,708,1,0,0,0,708,113,1,0,0,0,709,707,
        1,0,0,0,710,711,3,116,58,0,711,712,5,57,0,0,712,715,1,0,0,0,713,
        715,3,116,58,0,714,710,1,0,0,0,714,713,1,0,0,0,715,115,1,0,0,0,716,
        717,3,118,59,0,717,718,5,67,0,0,718,719,5,68,0,0,719,722,1,0,0,0,
        720,722,3,118,59,0,721,716,1,0,0,0,721,720,1,0,0,0,722,117,1,0,0,
        0,723,725,5,69,0,0,724,726,3,126,63,0,725,724,1,0,0,0,725,726,1,
        0,0,0,726,746,1,0,0,0,727,728,5,22,0,0,728,729,5,45,0,0,729,730,
        3,110,55,0,730,731,5,46,0,0,731,732,5,67,0,0,732,733,5,70,0,0,733,
        734,5,68,0,0,734,746,1,0,0,0,735,737,5,63,0,0,736,738,3,120,60,0,
        737,736,1,0,0,0,737,738,1,0,0,0,738,739,1,0,0,0,739,740,5,64,0,0,
        740,741,5,24,0,0,741,746,3,110,55,0,742,743,5,50,0,0,743,746,5,69,
        0,0,744,746,3,18,9,0,745,723,1,0,0,0,745,727,1,0,0,0,745,735,1,0,
        0,0,745,742,1,0,0,0,745,744,1,0,0,0,746,119,1,0,0,0,747,752,3,122,
        61,0,748,749,5,60,0,0,749,751,3,122,61,0,750,748,1,0,0,0,751,754,
        1,0,0,0,752,750,1,0,0,0,752,753,1,0,0,0,753,121,1,0,0,0,754,752,
        1,0,0,0,755,756,5,69,0,0,756,757,5,58,0,0,757,758,3,110,55,0,758,
        123,1,0,0,0,759,760,5,45,0,0,760,765,5,69,0,0,761,762,5,60,0,0,762,
        764,5,69,0,0,763,761,1,0,0,0,764,767,1,0,0,0,765,763,1,0,0,0,765,
        766,1,0,0,0,766,768,1,0,0,0,767,765,1,0,0,0,768,769,5,46,0,0,769,
        125,1,0,0,0,770,771,5,45,0,0,771,776,3,110,55,0,772,773,5,60,0,0,
        773,775,3,110,55,0,774,772,1,0,0,0,775,778,1,0,0,0,776,774,1,0,0,
        0,776,777,1,0,0,0,777,779,1,0,0,0,778,776,1,0,0,0,779,780,5,46,0,
        0,780,127,1,0,0,0,79,131,151,154,160,167,170,176,186,195,201,206,
        216,225,230,235,240,245,247,253,269,276,294,299,304,312,316,326,
        330,345,384,391,396,404,412,420,428,436,444,452,460,468,476,484,
        490,497,504,512,529,532,536,541,546,550,555,559,566,574,581,592,
        598,610,614,630,642,653,656,667,678,682,695,707,714,721,725,737,
        745,752,765,776
    ]

class EzLangParser ( Parser ):

    grammarFileName = "EzLang.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'let'", "'const'", "'static'", "'struct'", 
                     "'type'", "'declare'", "'loop'", "'await'", "'async'", 
                     "'break'", "'continue'", "'import'", "'export'", "'from'", 
                     "'match'", "'catch'", "'throw'", "'typeof'", "'return'", 
                     "'in'", "'as'", "'Vec'", "<INVALID>", "'=>'", "'->'", 
                     "'...'", "'<<='", "'>>='", "'+='", "'-='", "'*='", 
                     "'/='", "'%='", "'&='", "'|='", "'^='", "'<<'", "'>>'", 
                     "'=='", "'!='", "'<='", "'>='", "'&&'", "'||'", "'<'", 
                     "'>'", "'='", "'+'", "'-'", "'*'", "'/'", "'%'", "'&'", 
                     "'|'", "'^'", "'!'", "'?'", "':'", "';'", "','", "'.'", 
                     "'@'", "'('", "')'", "'{'", "'}'", "'['", "']'" ]

    symbolicNames = [ "<INVALID>", "LET", "CONST", "STATIC", "STRUCT", "TYPE", 
                      "DECLARE", "LOOP", "AWAIT", "ASYNC", "BREAK", "CONTINUE", 
                      "IMPORT", "EXPORT", "FROM", "MATCH", "CATCH", "THROW", 
                      "TYPEOF", "RETURN", "IN", "AS", "VEC", "BOOL_LIT", 
                      "FAT_ARROW", "PIPE_ARROW", "DOTDOTDOT", "SHL_ASSIGN", 
                      "SHR_ASSIGN", "PLUS_ASSIGN", "MINUS_ASSIGN", "STAR_ASSIGN", 
                      "SLASH_ASSIGN", "PERCENT_ASSIGN", "AMP_ASSIGN", "PIPE_ASSIGN", 
                      "CARET_ASSIGN", "SHL", "SHR", "EQUAL", "NOT_EQUAL", 
                      "LTE", "GTE", "AND", "OR", "LT", "GT", "ASSIGN", "PLUS", 
                      "MINUS", "STAR", "SLASH", "PERCENT", "AMP", "BIT_OR", 
                      "CARET", "BANG", "QUESTION", "COLON", "SEMI", "COMMA", 
                      "DOT", "AT", "LPAREN", "RPAREN", "LBRACE", "RBRACE", 
                      "LBRACKET", "RBRACKET", "IDENT", "INT_LIT", "FLOAT_LIT", 
                      "STRING", "WS", "LINE_COMMENT", "BLOCK_COMMENT" ]

    RULE_program = 0
    RULE_topLevelStatement = 1
    RULE_statement = 2
    RULE_letDecl = 3
    RULE_constDecl = 4
    RULE_staticDecl = 5
    RULE_structDef = 6
    RULE_structMember = 7
    RULE_typeDef = 8
    RULE_shapeType = 9
    RULE_shapeMember = 10
    RULE_declareStmt = 11
    RULE_importStmt = 12
    RULE_importItem = 13
    RULE_exportStmt = 14
    RULE_returnStmt = 15
    RULE_throwStmt = 16
    RULE_breakStmt = 17
    RULE_continueStmt = 18
    RULE_exprStmt = 19
    RULE_decorator = 20
    RULE_expression = 21
    RULE_assignExpr = 22
    RULE_assignOp = 23
    RULE_conditionalExpr = 24
    RULE_pipeExpr = 25
    RULE_orExpr = 26
    RULE_andExpr = 27
    RULE_bitOrExpr = 28
    RULE_bitXorExpr = 29
    RULE_bitAndExpr = 30
    RULE_eqExpr = 31
    RULE_compExpr = 32
    RULE_shiftExpr = 33
    RULE_addExpr = 34
    RULE_mulExpr = 35
    RULE_unaryExpr = 36
    RULE_postfixExpr = 37
    RULE_postfix = 38
    RULE_primaryExpr = 39
    RULE_lambdaExpr = 40
    RULE_paramList = 41
    RULE_param = 42
    RULE_namedArgList = 43
    RULE_namedArg = 44
    RULE_block = 45
    RULE_matchExpr = 46
    RULE_matchArm = 47
    RULE_loopExpr = 48
    RULE_catchExpr = 49
    RULE_arrayLiteral = 50
    RULE_vecLiteral = 51
    RULE_dictLiteral = 52
    RULE_dictEntry = 53
    RULE_typeofExpr = 54
    RULE_typeExpr = 55
    RULE_unionType = 56
    RULE_optionalType = 57
    RULE_arrayType = 58
    RULE_atomicType = 59
    RULE_paramTypeList = 60
    RULE_paramType = 61
    RULE_typeParams = 62
    RULE_typeArgs = 63

    ruleNames =  [ "program", "topLevelStatement", "statement", "letDecl", 
                   "constDecl", "staticDecl", "structDef", "structMember", 
                   "typeDef", "shapeType", "shapeMember", "declareStmt", 
                   "importStmt", "importItem", "exportStmt", "returnStmt", 
                   "throwStmt", "breakStmt", "continueStmt", "exprStmt", 
                   "decorator", "expression", "assignExpr", "assignOp", 
                   "conditionalExpr", "pipeExpr", "orExpr", "andExpr", "bitOrExpr", 
                   "bitXorExpr", "bitAndExpr", "eqExpr", "compExpr", "shiftExpr", 
                   "addExpr", "mulExpr", "unaryExpr", "postfixExpr", "postfix", 
                   "primaryExpr", "lambdaExpr", "paramList", "param", "namedArgList", 
                   "namedArg", "block", "matchExpr", "matchArm", "loopExpr", 
                   "catchExpr", "arrayLiteral", "vecLiteral", "dictLiteral", 
                   "dictEntry", "typeofExpr", "typeExpr", "unionType", "optionalType", 
                   "arrayType", "atomicType", "paramTypeList", "paramType", 
                   "typeParams", "typeArgs" ]

    EOF = Token.EOF
    LET=1
    CONST=2
    STATIC=3
    STRUCT=4
    TYPE=5
    DECLARE=6
    LOOP=7
    AWAIT=8
    ASYNC=9
    BREAK=10
    CONTINUE=11
    IMPORT=12
    EXPORT=13
    FROM=14
    MATCH=15
    CATCH=16
    THROW=17
    TYPEOF=18
    RETURN=19
    IN=20
    AS=21
    VEC=22
    BOOL_LIT=23
    FAT_ARROW=24
    PIPE_ARROW=25
    DOTDOTDOT=26
    SHL_ASSIGN=27
    SHR_ASSIGN=28
    PLUS_ASSIGN=29
    MINUS_ASSIGN=30
    STAR_ASSIGN=31
    SLASH_ASSIGN=32
    PERCENT_ASSIGN=33
    AMP_ASSIGN=34
    PIPE_ASSIGN=35
    CARET_ASSIGN=36
    SHL=37
    SHR=38
    EQUAL=39
    NOT_EQUAL=40
    LTE=41
    GTE=42
    AND=43
    OR=44
    LT=45
    GT=46
    ASSIGN=47
    PLUS=48
    MINUS=49
    STAR=50
    SLASH=51
    PERCENT=52
    AMP=53
    BIT_OR=54
    CARET=55
    BANG=56
    QUESTION=57
    COLON=58
    SEMI=59
    COMMA=60
    DOT=61
    AT=62
    LPAREN=63
    RPAREN=64
    LBRACE=65
    RBRACE=66
    LBRACKET=67
    RBRACKET=68
    IDENT=69
    INT_LIT=70
    FLOAT_LIT=71
    STRING=72
    WS=73
    LINE_COMMENT=74
    BLOCK_COMMENT=75

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ProgramContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(EzLangParser.EOF, 0)

        def topLevelStatement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.TopLevelStatementContext)
            else:
                return self.getTypedRuleContext(EzLangParser.TopLevelStatementContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_program

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitProgram" ):
                return visitor.visitProgram(self)
            else:
                return visitor.visitChildren(self)




    def program(self):

        localctx = EzLangParser.ProgramContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_program)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 131
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & -4539030290050322434) != 0) or ((((_la - 65)) & ~0x3f) == 0 and ((1 << (_la - 65)) & 245) != 0):
                self.state = 128
                self.topLevelStatement()
                self.state = 133
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 134
            self.match(EzLangParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TopLevelStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def statement(self):
            return self.getTypedRuleContext(EzLangParser.StatementContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_topLevelStatement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTopLevelStatement" ):
                return visitor.visitTopLevelStatement(self)
            else:
                return visitor.visitChildren(self)




    def topLevelStatement(self):

        localctx = EzLangParser.TopLevelStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_topLevelStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 136
            self.statement()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def letDecl(self):
            return self.getTypedRuleContext(EzLangParser.LetDeclContext,0)


        def constDecl(self):
            return self.getTypedRuleContext(EzLangParser.ConstDeclContext,0)


        def staticDecl(self):
            return self.getTypedRuleContext(EzLangParser.StaticDeclContext,0)


        def structDef(self):
            return self.getTypedRuleContext(EzLangParser.StructDefContext,0)


        def typeDef(self):
            return self.getTypedRuleContext(EzLangParser.TypeDefContext,0)


        def declareStmt(self):
            return self.getTypedRuleContext(EzLangParser.DeclareStmtContext,0)


        def importStmt(self):
            return self.getTypedRuleContext(EzLangParser.ImportStmtContext,0)


        def exportStmt(self):
            return self.getTypedRuleContext(EzLangParser.ExportStmtContext,0)


        def returnStmt(self):
            return self.getTypedRuleContext(EzLangParser.ReturnStmtContext,0)


        def throwStmt(self):
            return self.getTypedRuleContext(EzLangParser.ThrowStmtContext,0)


        def breakStmt(self):
            return self.getTypedRuleContext(EzLangParser.BreakStmtContext,0)


        def continueStmt(self):
            return self.getTypedRuleContext(EzLangParser.ContinueStmtContext,0)


        def exprStmt(self):
            return self.getTypedRuleContext(EzLangParser.ExprStmtContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStatement" ):
                return visitor.visitStatement(self)
            else:
                return visitor.visitChildren(self)




    def statement(self):

        localctx = EzLangParser.StatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_statement)
        try:
            self.state = 151
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,1,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 138
                self.letDecl()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 139
                self.constDecl()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 140
                self.staticDecl()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 141
                self.structDef()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 142
                self.typeDef()
                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 143
                self.declareStmt()
                pass

            elif la_ == 7:
                self.enterOuterAlt(localctx, 7)
                self.state = 144
                self.importStmt()
                pass

            elif la_ == 8:
                self.enterOuterAlt(localctx, 8)
                self.state = 145
                self.exportStmt()
                pass

            elif la_ == 9:
                self.enterOuterAlt(localctx, 9)
                self.state = 146
                self.returnStmt()
                pass

            elif la_ == 10:
                self.enterOuterAlt(localctx, 10)
                self.state = 147
                self.throwStmt()
                pass

            elif la_ == 11:
                self.enterOuterAlt(localctx, 11)
                self.state = 148
                self.breakStmt()
                pass

            elif la_ == 12:
                self.enterOuterAlt(localctx, 12)
                self.state = 149
                self.continueStmt()
                pass

            elif la_ == 13:
                self.enterOuterAlt(localctx, 13)
                self.state = 150
                self.exprStmt()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LetDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LET(self):
            return self.getToken(EzLangParser.LET, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def decorator(self):
            return self.getTypedRuleContext(EzLangParser.DecoratorContext,0)


        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_letDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLetDecl" ):
                return visitor.visitLetDecl(self)
            else:
                return visitor.visitChildren(self)




    def letDecl(self):

        localctx = EzLangParser.LetDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_letDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 154
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==62:
                self.state = 153
                self.decorator()


            self.state = 156
            self.match(EzLangParser.LET)
            self.state = 157
            self.match(EzLangParser.IDENT)
            self.state = 160
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==58:
                self.state = 158
                self.match(EzLangParser.COLON)
                self.state = 159
                self.typeExpr()


            self.state = 162
            self.match(EzLangParser.ASSIGN)
            self.state = 163
            self.expression()
            self.state = 164
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ConstDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CONST(self):
            return self.getToken(EzLangParser.CONST, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def decorator(self):
            return self.getTypedRuleContext(EzLangParser.DecoratorContext,0)


        def ASYNC(self):
            return self.getToken(EzLangParser.ASYNC, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_constDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitConstDecl" ):
                return visitor.visitConstDecl(self)
            else:
                return visitor.visitChildren(self)




    def constDecl(self):

        localctx = EzLangParser.ConstDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_constDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 167
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==62:
                self.state = 166
                self.decorator()


            self.state = 170
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==9:
                self.state = 169
                self.match(EzLangParser.ASYNC)


            self.state = 172
            self.match(EzLangParser.CONST)
            self.state = 173
            self.match(EzLangParser.IDENT)
            self.state = 176
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==58:
                self.state = 174
                self.match(EzLangParser.COLON)
                self.state = 175
                self.typeExpr()


            self.state = 178
            self.match(EzLangParser.ASSIGN)
            self.state = 179
            self.expression()
            self.state = 180
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StaticDeclContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STATIC(self):
            return self.getToken(EzLangParser.STATIC, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_staticDecl

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStaticDecl" ):
                return visitor.visitStaticDecl(self)
            else:
                return visitor.visitChildren(self)




    def staticDecl(self):

        localctx = EzLangParser.StaticDeclContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_staticDecl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 182
            self.match(EzLangParser.STATIC)
            self.state = 183
            self.match(EzLangParser.IDENT)
            self.state = 186
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==58:
                self.state = 184
                self.match(EzLangParser.COLON)
                self.state = 185
                self.typeExpr()


            self.state = 188
            self.match(EzLangParser.ASSIGN)
            self.state = 189
            self.expression()
            self.state = 190
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructDefContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRUCT(self):
            return self.getToken(EzLangParser.STRUCT, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def typeParams(self):
            return self.getTypedRuleContext(EzLangParser.TypeParamsContext,0)


        def structMember(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.StructMemberContext)
            else:
                return self.getTypedRuleContext(EzLangParser.StructMemberContext,i)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_structDef

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructDef" ):
                return visitor.visitStructDef(self)
            else:
                return visitor.visitChildren(self)




    def structDef(self):

        localctx = EzLangParser.StructDefContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_structDef)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 192
            self.match(EzLangParser.STRUCT)
            self.state = 193
            self.match(EzLangParser.IDENT)
            self.state = 195
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==45:
                self.state = 194
                self.typeParams()


            self.state = 197
            self.match(EzLangParser.LBRACE)
            self.state = 201
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==26 or _la==69:
                self.state = 198
                self.structMember()
                self.state = 203
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 204
            self.match(EzLangParser.RBRACE)
            self.state = 206
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==59:
                self.state = 205
                self.match(EzLangParser.SEMI)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructMemberContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DOTDOTDOT(self):
            return self.getToken(EzLangParser.DOTDOTDOT, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_structMember

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructMember" ):
                return visitor.visitStructMember(self)
            else:
                return visitor.visitChildren(self)




    def structMember(self):

        localctx = EzLangParser.StructMemberContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_structMember)
        self._la = 0 # Token type
        try:
            self.state = 225
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,12,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 208
                self.match(EzLangParser.DOTDOTDOT)
                self.state = 209
                self.match(EzLangParser.IDENT)
                self.state = 210
                self.match(EzLangParser.SEMI)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 211
                self.match(EzLangParser.IDENT)
                self.state = 212
                self.match(EzLangParser.COLON)
                self.state = 213
                self.typeExpr()
                self.state = 216
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==47:
                    self.state = 214
                    self.match(EzLangParser.ASSIGN)
                    self.state = 215
                    self.expression()


                self.state = 218
                self.match(EzLangParser.SEMI)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 220
                self.match(EzLangParser.IDENT)
                self.state = 221
                self.match(EzLangParser.ASSIGN)
                self.state = 222
                self.expression()
                self.state = 223
                self.match(EzLangParser.SEMI)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeDefContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def TYPE(self):
            return self.getToken(EzLangParser.TYPE, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def shapeType(self):
            return self.getTypedRuleContext(EzLangParser.ShapeTypeContext,0)


        def typeParams(self):
            return self.getTypedRuleContext(EzLangParser.TypeParamsContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_typeDef

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTypeDef" ):
                return visitor.visitTypeDef(self)
            else:
                return visitor.visitChildren(self)




    def typeDef(self):

        localctx = EzLangParser.TypeDefContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_typeDef)
        self._la = 0 # Token type
        try:
            self.state = 247
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,17,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 227
                self.match(EzLangParser.TYPE)
                self.state = 228
                self.match(EzLangParser.IDENT)
                self.state = 230
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==45:
                    self.state = 229
                    self.typeParams()


                self.state = 232
                self.match(EzLangParser.ASSIGN)
                self.state = 233
                self.shapeType()
                self.state = 235
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==59:
                    self.state = 234
                    self.match(EzLangParser.SEMI)


                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 237
                self.match(EzLangParser.TYPE)
                self.state = 238
                self.match(EzLangParser.IDENT)
                self.state = 240
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==45:
                    self.state = 239
                    self.typeParams()


                self.state = 242
                self.match(EzLangParser.ASSIGN)
                self.state = 243
                self.typeExpr()
                self.state = 245
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==59:
                    self.state = 244
                    self.match(EzLangParser.SEMI)


                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ShapeTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def shapeMember(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ShapeMemberContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ShapeMemberContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_shapeType

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitShapeType" ):
                return visitor.visitShapeType(self)
            else:
                return visitor.visitChildren(self)




    def shapeType(self):

        localctx = EzLangParser.ShapeTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_shapeType)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 249
            self.match(EzLangParser.LBRACE)
            self.state = 253
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while ((((_la - 26)) & ~0x3f) == 0 and ((1 << (_la - 26)) & 10995116277761) != 0):
                self.state = 250
                self.shapeMember()
                self.state = 255
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 256
            self.match(EzLangParser.RBRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ShapeMemberContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DOTDOTDOT(self):
            return self.getToken(EzLangParser.DOTDOTDOT, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def LBRACKET(self):
            return self.getToken(EzLangParser.LBRACKET, 0)

        def COLON(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COLON)
            else:
                return self.getToken(EzLangParser.COLON, i)

        def typeExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.TypeExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.TypeExprContext,i)


        def RBRACKET(self):
            return self.getToken(EzLangParser.RBRACKET, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_shapeMember

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitShapeMember" ):
                return visitor.visitShapeMember(self)
            else:
                return visitor.visitChildren(self)




    def shapeMember(self):

        localctx = EzLangParser.ShapeMemberContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_shapeMember)
        self._la = 0 # Token type
        try:
            self.state = 276
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [26]:
                self.enterOuterAlt(localctx, 1)
                self.state = 258
                self.match(EzLangParser.DOTDOTDOT)
                self.state = 259
                self.match(EzLangParser.IDENT)
                self.state = 260
                self.match(EzLangParser.SEMI)
                pass
            elif token in [67]:
                self.enterOuterAlt(localctx, 2)
                self.state = 261
                self.match(EzLangParser.LBRACKET)
                self.state = 262
                self.match(EzLangParser.IDENT)
                self.state = 263
                self.match(EzLangParser.COLON)
                self.state = 264
                self.typeExpr()
                self.state = 265
                self.match(EzLangParser.RBRACKET)
                self.state = 266
                self.match(EzLangParser.COLON)
                self.state = 267
                self.typeExpr()
                self.state = 269
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==59:
                    self.state = 268
                    self.match(EzLangParser.SEMI)


                pass
            elif token in [69]:
                self.enterOuterAlt(localctx, 3)
                self.state = 271
                self.match(EzLangParser.IDENT)
                self.state = 272
                self.match(EzLangParser.COLON)
                self.state = 273
                self.typeExpr()
                self.state = 274
                self.match(EzLangParser.SEMI)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DeclareStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DECLARE(self):
            return self.getToken(EzLangParser.DECLARE, 0)

        def CONST(self):
            return self.getToken(EzLangParser.CONST, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_declareStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDeclareStmt" ):
                return visitor.visitDeclareStmt(self)
            else:
                return visitor.visitChildren(self)




    def declareStmt(self):

        localctx = EzLangParser.DeclareStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_declareStmt)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 278
            self.match(EzLangParser.DECLARE)
            self.state = 279
            self.match(EzLangParser.CONST)
            self.state = 280
            self.match(EzLangParser.IDENT)
            self.state = 281
            self.match(EzLangParser.COLON)
            self.state = 282
            self.typeExpr()
            self.state = 283
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ImportStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def FROM(self):
            return self.getToken(EzLangParser.FROM, 0)

        def STRING(self):
            return self.getToken(EzLangParser.STRING, 0)

        def IMPORT(self):
            return self.getToken(EzLangParser.IMPORT, 0)

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def importItem(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ImportItemContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ImportItemContext,i)


        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_importStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitImportStmt" ):
                return visitor.visitImportStmt(self)
            else:
                return visitor.visitChildren(self)




    def importStmt(self):

        localctx = EzLangParser.ImportStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_importStmt)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 285
            self.match(EzLangParser.FROM)
            self.state = 286
            self.match(EzLangParser.STRING)
            self.state = 287
            self.match(EzLangParser.IMPORT)
            self.state = 288
            self.match(EzLangParser.LBRACE)
            self.state = 289
            self.importItem()
            self.state = 294
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==60:
                self.state = 290
                self.match(EzLangParser.COMMA)
                self.state = 291
                self.importItem()
                self.state = 296
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 297
            self.match(EzLangParser.RBRACE)
            self.state = 299
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==59:
                self.state = 298
                self.match(EzLangParser.SEMI)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ImportItemContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.IDENT)
            else:
                return self.getToken(EzLangParser.IDENT, i)

        def AS(self):
            return self.getToken(EzLangParser.AS, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_importItem

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitImportItem" ):
                return visitor.visitImportItem(self)
            else:
                return visitor.visitChildren(self)




    def importItem(self):

        localctx = EzLangParser.ImportItemContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_importItem)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 301
            self.match(EzLangParser.IDENT)
            self.state = 304
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==21:
                self.state = 302
                self.match(EzLangParser.AS)
                self.state = 303
                self.match(EzLangParser.IDENT)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExportStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EXPORT(self):
            return self.getToken(EzLangParser.EXPORT, 0)

        def letDecl(self):
            return self.getTypedRuleContext(EzLangParser.LetDeclContext,0)


        def constDecl(self):
            return self.getTypedRuleContext(EzLangParser.ConstDeclContext,0)


        def staticDecl(self):
            return self.getTypedRuleContext(EzLangParser.StaticDeclContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_exportStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExportStmt" ):
                return visitor.visitExportStmt(self)
            else:
                return visitor.visitChildren(self)




    def exportStmt(self):

        localctx = EzLangParser.ExportStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_exportStmt)
        try:
            self.state = 312
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,24,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 306
                self.match(EzLangParser.EXPORT)
                self.state = 307
                self.letDecl()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 308
                self.match(EzLangParser.EXPORT)
                self.state = 309
                self.constDecl()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 310
                self.match(EzLangParser.EXPORT)
                self.state = 311
                self.staticDecl()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ReturnStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def RETURN(self):
            return self.getToken(EzLangParser.RETURN, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_returnStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitReturnStmt" ):
                return visitor.visitReturnStmt(self)
            else:
                return visitor.visitChildren(self)




    def returnStmt(self):

        localctx = EzLangParser.ReturnStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_returnStmt)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 314
            self.match(EzLangParser.RETURN)
            self.state = 316
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & -9150716308478393984) != 0) or ((((_la - 65)) & ~0x3f) == 0 and ((1 << (_la - 65)) & 245) != 0):
                self.state = 315
                self.expression()


            self.state = 318
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ThrowStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def THROW(self):
            return self.getToken(EzLangParser.THROW, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_throwStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitThrowStmt" ):
                return visitor.visitThrowStmt(self)
            else:
                return visitor.visitChildren(self)




    def throwStmt(self):

        localctx = EzLangParser.ThrowStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_throwStmt)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 320
            self.match(EzLangParser.THROW)
            self.state = 321
            self.expression()
            self.state = 322
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BreakStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BREAK(self):
            return self.getToken(EzLangParser.BREAK, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_breakStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBreakStmt" ):
                return visitor.visitBreakStmt(self)
            else:
                return visitor.visitChildren(self)




    def breakStmt(self):

        localctx = EzLangParser.BreakStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_breakStmt)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 324
            self.match(EzLangParser.BREAK)
            self.state = 326
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==59:
                self.state = 325
                self.match(EzLangParser.SEMI)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ContinueStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CONTINUE(self):
            return self.getToken(EzLangParser.CONTINUE, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_continueStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitContinueStmt" ):
                return visitor.visitContinueStmt(self)
            else:
                return visitor.visitChildren(self)




    def continueStmt(self):

        localctx = EzLangParser.ContinueStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 36, self.RULE_continueStmt)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 328
            self.match(EzLangParser.CONTINUE)
            self.state = 330
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==59:
                self.state = 329
                self.match(EzLangParser.SEMI)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExprStmtContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_exprStmt

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExprStmt" ):
                return visitor.visitExprStmt(self)
            else:
                return visitor.visitChildren(self)




    def exprStmt(self):

        localctx = EzLangParser.ExprStmtContext(self, self._ctx, self.state)
        self.enterRule(localctx, 38, self.RULE_exprStmt)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 332
            self.expression()
            self.state = 333
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DecoratorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def AT(self):
            return self.getToken(EzLangParser.AT, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_decorator

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDecorator" ):
                return visitor.visitDecorator(self)
            else:
                return visitor.visitChildren(self)




    def decorator(self):

        localctx = EzLangParser.DecoratorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 40, self.RULE_decorator)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 335
            self.match(EzLangParser.AT)
            self.state = 336
            self.match(EzLangParser.IDENT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignExpr(self):
            return self.getTypedRuleContext(EzLangParser.AssignExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExpression" ):
                return visitor.visitExpression(self)
            else:
                return visitor.visitChildren(self)




    def expression(self):

        localctx = EzLangParser.ExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 42, self.RULE_expression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 338
            self.assignExpr()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssignExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def conditionalExpr(self):
            return self.getTypedRuleContext(EzLangParser.ConditionalExprContext,0)


        def assignOp(self):
            return self.getTypedRuleContext(EzLangParser.AssignOpContext,0)


        def assignExpr(self):
            return self.getTypedRuleContext(EzLangParser.AssignExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_assignExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignExpr" ):
                return visitor.visitAssignExpr(self)
            else:
                return visitor.visitChildren(self)




    def assignExpr(self):

        localctx = EzLangParser.AssignExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 44, self.RULE_assignExpr)
        try:
            self.state = 345
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,28,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 340
                self.conditionalExpr()
                self.state = 341
                self.assignOp()
                self.state = 342
                self.assignExpr()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 344
                self.conditionalExpr()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssignOpContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def PLUS_ASSIGN(self):
            return self.getToken(EzLangParser.PLUS_ASSIGN, 0)

        def MINUS_ASSIGN(self):
            return self.getToken(EzLangParser.MINUS_ASSIGN, 0)

        def STAR_ASSIGN(self):
            return self.getToken(EzLangParser.STAR_ASSIGN, 0)

        def SLASH_ASSIGN(self):
            return self.getToken(EzLangParser.SLASH_ASSIGN, 0)

        def PERCENT_ASSIGN(self):
            return self.getToken(EzLangParser.PERCENT_ASSIGN, 0)

        def AMP_ASSIGN(self):
            return self.getToken(EzLangParser.AMP_ASSIGN, 0)

        def PIPE_ASSIGN(self):
            return self.getToken(EzLangParser.PIPE_ASSIGN, 0)

        def CARET_ASSIGN(self):
            return self.getToken(EzLangParser.CARET_ASSIGN, 0)

        def SHL_ASSIGN(self):
            return self.getToken(EzLangParser.SHL_ASSIGN, 0)

        def SHR_ASSIGN(self):
            return self.getToken(EzLangParser.SHR_ASSIGN, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_assignOp

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignOp" ):
                return visitor.visitAssignOp(self)
            else:
                return visitor.visitChildren(self)




    def assignOp(self):

        localctx = EzLangParser.AssignOpContext(self, self._ctx, self.state)
        self.enterRule(localctx, 46, self.RULE_assignOp)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 347
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 140874793091072) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ConditionalExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def pipeExpr(self):
            return self.getTypedRuleContext(EzLangParser.PipeExprContext,0)


        def QUESTION(self):
            return self.getToken(EzLangParser.QUESTION, 0)

        def block(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.BlockContext)
            else:
                return self.getTypedRuleContext(EzLangParser.BlockContext,i)


        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def conditionalExpr(self):
            return self.getTypedRuleContext(EzLangParser.ConditionalExprContext,0)


        def BREAK(self):
            return self.getToken(EzLangParser.BREAK, 0)

        def CONTINUE(self):
            return self.getToken(EzLangParser.CONTINUE, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_conditionalExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitConditionalExpr" ):
                return visitor.visitConditionalExpr(self)
            else:
                return visitor.visitChildren(self)




    def conditionalExpr(self):

        localctx = EzLangParser.ConditionalExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 48, self.RULE_conditionalExpr)
        try:
            self.state = 384
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,29,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 349
                self.pipeExpr()
                self.state = 350
                self.match(EzLangParser.QUESTION)
                self.state = 351
                self.block()
                self.state = 352
                self.match(EzLangParser.COLON)
                self.state = 353
                self.conditionalExpr()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 355
                self.pipeExpr()
                self.state = 356
                self.match(EzLangParser.QUESTION)
                self.state = 357
                self.block()
                self.state = 358
                self.match(EzLangParser.COLON)
                self.state = 359
                self.block()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 361
                self.pipeExpr()
                self.state = 362
                self.match(EzLangParser.QUESTION)
                self.state = 363
                self.block()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 365
                self.pipeExpr()
                self.state = 366
                self.match(EzLangParser.QUESTION)
                self.state = 367
                self.match(EzLangParser.BREAK)
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 369
                self.pipeExpr()
                self.state = 370
                self.match(EzLangParser.QUESTION)
                self.state = 371
                self.match(EzLangParser.CONTINUE)
                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 373
                self.pipeExpr()
                self.state = 374
                self.match(EzLangParser.QUESTION)
                self.state = 375
                self.expression()
                self.state = 376
                self.match(EzLangParser.COLON)
                self.state = 377
                self.expression()
                pass

            elif la_ == 7:
                self.enterOuterAlt(localctx, 7)
                self.state = 379
                self.pipeExpr()
                self.state = 380
                self.match(EzLangParser.QUESTION)
                self.state = 381
                self.expression()
                pass

            elif la_ == 8:
                self.enterOuterAlt(localctx, 8)
                self.state = 383
                self.pipeExpr()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PipeExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def orExpr(self):
            return self.getTypedRuleContext(EzLangParser.OrExprContext,0)


        def PIPE_ARROW(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.PIPE_ARROW)
            else:
                return self.getToken(EzLangParser.PIPE_ARROW, i)

        def IDENT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.IDENT)
            else:
                return self.getToken(EzLangParser.IDENT, i)

        def LPAREN(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.LPAREN)
            else:
                return self.getToken(EzLangParser.LPAREN, i)

        def RPAREN(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.RPAREN)
            else:
                return self.getToken(EzLangParser.RPAREN, i)

        def namedArgList(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.NamedArgListContext)
            else:
                return self.getTypedRuleContext(EzLangParser.NamedArgListContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_pipeExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPipeExpr" ):
                return visitor.visitPipeExpr(self)
            else:
                return visitor.visitChildren(self)




    def pipeExpr(self):

        localctx = EzLangParser.PipeExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 50, self.RULE_pipeExpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 386
            self.orExpr()
            self.state = 396
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,31,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 387
                    self.match(EzLangParser.PIPE_ARROW)
                    self.state = 388
                    self.match(EzLangParser.IDENT)
                    self.state = 389
                    self.match(EzLangParser.LPAREN)
                    self.state = 391
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==26 or _la==69:
                        self.state = 390
                        self.namedArgList()


                    self.state = 393
                    self.match(EzLangParser.RPAREN) 
                self.state = 398
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,31,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class OrExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def andExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.AndExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.AndExprContext,i)


        def OR(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.OR)
            else:
                return self.getToken(EzLangParser.OR, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_orExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitOrExpr" ):
                return visitor.visitOrExpr(self)
            else:
                return visitor.visitChildren(self)




    def orExpr(self):

        localctx = EzLangParser.OrExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 52, self.RULE_orExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 399
            self.andExpr()
            self.state = 404
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,32,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 400
                    self.match(EzLangParser.OR)
                    self.state = 401
                    self.andExpr() 
                self.state = 406
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,32,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AndExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def bitOrExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.BitOrExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.BitOrExprContext,i)


        def AND(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.AND)
            else:
                return self.getToken(EzLangParser.AND, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_andExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAndExpr" ):
                return visitor.visitAndExpr(self)
            else:
                return visitor.visitChildren(self)




    def andExpr(self):

        localctx = EzLangParser.AndExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 54, self.RULE_andExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 407
            self.bitOrExpr()
            self.state = 412
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,33,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 408
                    self.match(EzLangParser.AND)
                    self.state = 409
                    self.bitOrExpr() 
                self.state = 414
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,33,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BitOrExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def bitXorExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.BitXorExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.BitXorExprContext,i)


        def BIT_OR(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.BIT_OR)
            else:
                return self.getToken(EzLangParser.BIT_OR, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_bitOrExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBitOrExpr" ):
                return visitor.visitBitOrExpr(self)
            else:
                return visitor.visitChildren(self)




    def bitOrExpr(self):

        localctx = EzLangParser.BitOrExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 56, self.RULE_bitOrExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 415
            self.bitXorExpr()
            self.state = 420
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,34,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 416
                    self.match(EzLangParser.BIT_OR)
                    self.state = 417
                    self.bitXorExpr() 
                self.state = 422
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,34,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BitXorExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def bitAndExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.BitAndExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.BitAndExprContext,i)


        def CARET(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.CARET)
            else:
                return self.getToken(EzLangParser.CARET, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_bitXorExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBitXorExpr" ):
                return visitor.visitBitXorExpr(self)
            else:
                return visitor.visitChildren(self)




    def bitXorExpr(self):

        localctx = EzLangParser.BitXorExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 58, self.RULE_bitXorExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 423
            self.bitAndExpr()
            self.state = 428
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,35,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 424
                    self.match(EzLangParser.CARET)
                    self.state = 425
                    self.bitAndExpr() 
                self.state = 430
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,35,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BitAndExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def eqExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.EqExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.EqExprContext,i)


        def AMP(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.AMP)
            else:
                return self.getToken(EzLangParser.AMP, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_bitAndExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBitAndExpr" ):
                return visitor.visitBitAndExpr(self)
            else:
                return visitor.visitChildren(self)




    def bitAndExpr(self):

        localctx = EzLangParser.BitAndExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 60, self.RULE_bitAndExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 431
            self.eqExpr()
            self.state = 436
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,36,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 432
                    self.match(EzLangParser.AMP)
                    self.state = 433
                    self.eqExpr() 
                self.state = 438
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,36,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EqExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def compExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.CompExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.CompExprContext,i)


        def EQUAL(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.EQUAL)
            else:
                return self.getToken(EzLangParser.EQUAL, i)

        def NOT_EQUAL(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.NOT_EQUAL)
            else:
                return self.getToken(EzLangParser.NOT_EQUAL, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_eqExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEqExpr" ):
                return visitor.visitEqExpr(self)
            else:
                return visitor.visitChildren(self)




    def eqExpr(self):

        localctx = EzLangParser.EqExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 62, self.RULE_eqExpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 439
            self.compExpr()
            self.state = 444
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,37,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 440
                    _la = self._input.LA(1)
                    if not(_la==39 or _la==40):
                        self._errHandler.recoverInline(self)
                    else:
                        self._errHandler.reportMatch(self)
                        self.consume()
                    self.state = 441
                    self.compExpr() 
                self.state = 446
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,37,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CompExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def shiftExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ShiftExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ShiftExprContext,i)


        def LT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.LT)
            else:
                return self.getToken(EzLangParser.LT, i)

        def GT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.GT)
            else:
                return self.getToken(EzLangParser.GT, i)

        def LTE(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.LTE)
            else:
                return self.getToken(EzLangParser.LTE, i)

        def GTE(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.GTE)
            else:
                return self.getToken(EzLangParser.GTE, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_compExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompExpr" ):
                return visitor.visitCompExpr(self)
            else:
                return visitor.visitChildren(self)




    def compExpr(self):

        localctx = EzLangParser.CompExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 64, self.RULE_compExpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 447
            self.shiftExpr()
            self.state = 452
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,38,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 448
                    _la = self._input.LA(1)
                    if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 112150186033152) != 0)):
                        self._errHandler.recoverInline(self)
                    else:
                        self._errHandler.reportMatch(self)
                        self.consume()
                    self.state = 449
                    self.shiftExpr() 
                self.state = 454
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,38,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ShiftExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def addExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.AddExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.AddExprContext,i)


        def SHL(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.SHL)
            else:
                return self.getToken(EzLangParser.SHL, i)

        def SHR(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.SHR)
            else:
                return self.getToken(EzLangParser.SHR, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_shiftExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitShiftExpr" ):
                return visitor.visitShiftExpr(self)
            else:
                return visitor.visitChildren(self)




    def shiftExpr(self):

        localctx = EzLangParser.ShiftExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 66, self.RULE_shiftExpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 455
            self.addExpr()
            self.state = 460
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,39,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 456
                    _la = self._input.LA(1)
                    if not(_la==37 or _la==38):
                        self._errHandler.recoverInline(self)
                    else:
                        self._errHandler.reportMatch(self)
                        self.consume()
                    self.state = 457
                    self.addExpr() 
                self.state = 462
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,39,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AddExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def mulExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MulExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MulExprContext,i)


        def PLUS(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.PLUS)
            else:
                return self.getToken(EzLangParser.PLUS, i)

        def MINUS(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.MINUS)
            else:
                return self.getToken(EzLangParser.MINUS, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_addExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAddExpr" ):
                return visitor.visitAddExpr(self)
            else:
                return visitor.visitChildren(self)




    def addExpr(self):

        localctx = EzLangParser.AddExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 68, self.RULE_addExpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 463
            self.mulExpr()
            self.state = 468
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,40,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 464
                    _la = self._input.LA(1)
                    if not(_la==48 or _la==49):
                        self._errHandler.recoverInline(self)
                    else:
                        self._errHandler.reportMatch(self)
                        self.consume()
                    self.state = 465
                    self.mulExpr() 
                self.state = 470
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,40,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MulExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def unaryExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.UnaryExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.UnaryExprContext,i)


        def STAR(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.STAR)
            else:
                return self.getToken(EzLangParser.STAR, i)

        def SLASH(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.SLASH)
            else:
                return self.getToken(EzLangParser.SLASH, i)

        def PERCENT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.PERCENT)
            else:
                return self.getToken(EzLangParser.PERCENT, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_mulExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMulExpr" ):
                return visitor.visitMulExpr(self)
            else:
                return visitor.visitChildren(self)




    def mulExpr(self):

        localctx = EzLangParser.MulExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 70, self.RULE_mulExpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 471
            self.unaryExpr()
            self.state = 476
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,41,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 472
                    _la = self._input.LA(1)
                    if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 7881299347898368) != 0)):
                        self._errHandler.recoverInline(self)
                    else:
                        self._errHandler.reportMatch(self)
                        self.consume()
                    self.state = 473
                    self.unaryExpr() 
                self.state = 478
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,41,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class UnaryExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BANG(self):
            return self.getToken(EzLangParser.BANG, 0)

        def unaryExpr(self):
            return self.getTypedRuleContext(EzLangParser.UnaryExprContext,0)


        def MINUS(self):
            return self.getToken(EzLangParser.MINUS, 0)

        def postfixExpr(self):
            return self.getTypedRuleContext(EzLangParser.PostfixExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_unaryExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitUnaryExpr" ):
                return visitor.visitUnaryExpr(self)
            else:
                return visitor.visitChildren(self)




    def unaryExpr(self):

        localctx = EzLangParser.UnaryExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 72, self.RULE_unaryExpr)
        try:
            self.state = 484
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [56]:
                self.enterOuterAlt(localctx, 1)
                self.state = 479
                self.match(EzLangParser.BANG)
                self.state = 480
                self.unaryExpr()
                pass
            elif token in [49]:
                self.enterOuterAlt(localctx, 2)
                self.state = 481
                self.match(EzLangParser.MINUS)
                self.state = 482
                self.unaryExpr()
                pass
            elif token in [7, 8, 15, 16, 18, 22, 23, 45, 63, 65, 67, 69, 70, 71, 72]:
                self.enterOuterAlt(localctx, 3)
                self.state = 483
                self.postfixExpr()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PostfixExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def primaryExpr(self):
            return self.getTypedRuleContext(EzLangParser.PrimaryExprContext,0)


        def postfix(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.PostfixContext)
            else:
                return self.getTypedRuleContext(EzLangParser.PostfixContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_postfixExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPostfixExpr" ):
                return visitor.visitPostfixExpr(self)
            else:
                return visitor.visitChildren(self)




    def postfixExpr(self):

        localctx = EzLangParser.PostfixExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 74, self.RULE_postfixExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 486
            self.primaryExpr()
            self.state = 490
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,43,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 487
                    self.postfix() 
                self.state = 492
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,43,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PostfixContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DOT(self):
            return self.getToken(EzLangParser.DOT, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def namedArgList(self):
            return self.getTypedRuleContext(EzLangParser.NamedArgListContext,0)


        def LBRACKET(self):
            return self.getToken(EzLangParser.LBRACKET, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def RBRACKET(self):
            return self.getToken(EzLangParser.RBRACKET, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_postfix

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPostfix" ):
                return visitor.visitPostfix(self)
            else:
                return visitor.visitChildren(self)




    def postfix(self):

        localctx = EzLangParser.PostfixContext(self, self._ctx, self.state)
        self.enterRule(localctx, 76, self.RULE_postfix)
        self._la = 0 # Token type
        try:
            self.state = 504
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [61]:
                self.enterOuterAlt(localctx, 1)
                self.state = 493
                self.match(EzLangParser.DOT)
                self.state = 494
                self.match(EzLangParser.IDENT)
                pass
            elif token in [63]:
                self.enterOuterAlt(localctx, 2)
                self.state = 495
                self.match(EzLangParser.LPAREN)
                self.state = 497
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==26 or _la==69:
                    self.state = 496
                    self.namedArgList()


                self.state = 499
                self.match(EzLangParser.RPAREN)
                pass
            elif token in [67]:
                self.enterOuterAlt(localctx, 3)
                self.state = 500
                self.match(EzLangParser.LBRACKET)
                self.state = 501
                self.expression()
                self.state = 502
                self.match(EzLangParser.RBRACKET)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PrimaryExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def INT_LIT(self):
            return self.getToken(EzLangParser.INT_LIT, 0)

        def FLOAT_LIT(self):
            return self.getToken(EzLangParser.FLOAT_LIT, 0)

        def STRING(self):
            return self.getToken(EzLangParser.STRING, 0)

        def BOOL_LIT(self):
            return self.getToken(EzLangParser.BOOL_LIT, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def typeArgs(self):
            return self.getTypedRuleContext(EzLangParser.TypeArgsContext,0)


        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def lambdaExpr(self):
            return self.getTypedRuleContext(EzLangParser.LambdaExprContext,0)


        def matchExpr(self):
            return self.getTypedRuleContext(EzLangParser.MatchExprContext,0)


        def loopExpr(self):
            return self.getTypedRuleContext(EzLangParser.LoopExprContext,0)


        def catchExpr(self):
            return self.getTypedRuleContext(EzLangParser.CatchExprContext,0)


        def arrayLiteral(self):
            return self.getTypedRuleContext(EzLangParser.ArrayLiteralContext,0)


        def vecLiteral(self):
            return self.getTypedRuleContext(EzLangParser.VecLiteralContext,0)


        def dictLiteral(self):
            return self.getTypedRuleContext(EzLangParser.DictLiteralContext,0)


        def typeofExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeofExprContext,0)


        def AWAIT(self):
            return self.getToken(EzLangParser.AWAIT, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_primaryExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPrimaryExpr" ):
                return visitor.visitPrimaryExpr(self)
            else:
                return visitor.visitChildren(self)




    def primaryExpr(self):

        localctx = EzLangParser.PrimaryExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 78, self.RULE_primaryExpr)
        try:
            self.state = 529
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,47,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 506
                self.match(EzLangParser.INT_LIT)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 507
                self.match(EzLangParser.FLOAT_LIT)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 508
                self.match(EzLangParser.STRING)
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 509
                self.match(EzLangParser.BOOL_LIT)
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 510
                self.match(EzLangParser.IDENT)
                self.state = 512
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,46,self._ctx)
                if la_ == 1:
                    self.state = 511
                    self.typeArgs()


                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 514
                self.match(EzLangParser.LPAREN)
                self.state = 515
                self.expression()
                self.state = 516
                self.match(EzLangParser.RPAREN)
                pass

            elif la_ == 7:
                self.enterOuterAlt(localctx, 7)
                self.state = 518
                self.block()
                pass

            elif la_ == 8:
                self.enterOuterAlt(localctx, 8)
                self.state = 519
                self.lambdaExpr()
                pass

            elif la_ == 9:
                self.enterOuterAlt(localctx, 9)
                self.state = 520
                self.matchExpr()
                pass

            elif la_ == 10:
                self.enterOuterAlt(localctx, 10)
                self.state = 521
                self.loopExpr()
                pass

            elif la_ == 11:
                self.enterOuterAlt(localctx, 11)
                self.state = 522
                self.catchExpr()
                pass

            elif la_ == 12:
                self.enterOuterAlt(localctx, 12)
                self.state = 523
                self.arrayLiteral()
                pass

            elif la_ == 13:
                self.enterOuterAlt(localctx, 13)
                self.state = 524
                self.vecLiteral()
                pass

            elif la_ == 14:
                self.enterOuterAlt(localctx, 14)
                self.state = 525
                self.dictLiteral()
                pass

            elif la_ == 15:
                self.enterOuterAlt(localctx, 15)
                self.state = 526
                self.typeofExpr()
                pass

            elif la_ == 16:
                self.enterOuterAlt(localctx, 16)
                self.state = 527
                self.match(EzLangParser.AWAIT)
                self.state = 528
                self.expression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LambdaExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def FAT_ARROW(self):
            return self.getToken(EzLangParser.FAT_ARROW, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def typeParams(self):
            return self.getTypedRuleContext(EzLangParser.TypeParamsContext,0)


        def paramList(self):
            return self.getTypedRuleContext(EzLangParser.ParamListContext,0)


        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_lambdaExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLambdaExpr" ):
                return visitor.visitLambdaExpr(self)
            else:
                return visitor.visitChildren(self)




    def lambdaExpr(self):

        localctx = EzLangParser.LambdaExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 80, self.RULE_lambdaExpr)
        self._la = 0 # Token type
        try:
            self.state = 559
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,54,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 532
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==45:
                    self.state = 531
                    self.typeParams()


                self.state = 534
                self.match(EzLangParser.LPAREN)
                self.state = 536
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==69:
                    self.state = 535
                    self.paramList()


                self.state = 538
                self.match(EzLangParser.RPAREN)
                self.state = 541
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==58:
                    self.state = 539
                    self.match(EzLangParser.COLON)
                    self.state = 540
                    self.typeExpr()


                self.state = 543
                self.match(EzLangParser.FAT_ARROW)
                self.state = 544
                self.expression()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 546
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==45:
                    self.state = 545
                    self.typeParams()


                self.state = 548
                self.match(EzLangParser.LPAREN)
                self.state = 550
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==69:
                    self.state = 549
                    self.paramList()


                self.state = 552
                self.match(EzLangParser.RPAREN)
                self.state = 555
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==58:
                    self.state = 553
                    self.match(EzLangParser.COLON)
                    self.state = 554
                    self.typeExpr()


                self.state = 557
                self.match(EzLangParser.FAT_ARROW)
                self.state = 558
                self.block()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParamListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def param(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ParamContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ParamContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_paramList

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParamList" ):
                return visitor.visitParamList(self)
            else:
                return visitor.visitChildren(self)




    def paramList(self):

        localctx = EzLangParser.ParamListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 82, self.RULE_paramList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 561
            self.param()
            self.state = 566
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==60:
                self.state = 562
                self.match(EzLangParser.COMMA)
                self.state = 563
                self.param()
                self.state = 568
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParamContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_param

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParam" ):
                return visitor.visitParam(self)
            else:
                return visitor.visitChildren(self)




    def param(self):

        localctx = EzLangParser.ParamContext(self, self._ctx, self.state)
        self.enterRule(localctx, 84, self.RULE_param)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 569
            self.match(EzLangParser.IDENT)
            self.state = 570
            self.match(EzLangParser.COLON)
            self.state = 571
            self.typeExpr()
            self.state = 574
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==47:
                self.state = 572
                self.match(EzLangParser.ASSIGN)
                self.state = 573
                self.expression()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NamedArgListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def namedArg(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.NamedArgContext)
            else:
                return self.getTypedRuleContext(EzLangParser.NamedArgContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_namedArgList

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitNamedArgList" ):
                return visitor.visitNamedArgList(self)
            else:
                return visitor.visitChildren(self)




    def namedArgList(self):

        localctx = EzLangParser.NamedArgListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 86, self.RULE_namedArgList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 576
            self.namedArg()
            self.state = 581
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==60:
                self.state = 577
                self.match(EzLangParser.COMMA)
                self.state = 578
                self.namedArg()
                self.state = 583
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NamedArgContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def QUESTION(self):
            return self.getToken(EzLangParser.QUESTION, 0)

        def DOTDOTDOT(self):
            return self.getToken(EzLangParser.DOTDOTDOT, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_namedArg

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitNamedArg" ):
                return visitor.visitNamedArg(self)
            else:
                return visitor.visitChildren(self)




    def namedArg(self):

        localctx = EzLangParser.NamedArgContext(self, self._ctx, self.state)
        self.enterRule(localctx, 88, self.RULE_namedArg)
        try:
            self.state = 592
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,58,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 584
                self.match(EzLangParser.IDENT)
                self.state = 585
                self.match(EzLangParser.ASSIGN)
                self.state = 586
                self.expression()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 587
                self.match(EzLangParser.IDENT)
                self.state = 588
                self.match(EzLangParser.ASSIGN)
                self.state = 589
                self.match(EzLangParser.QUESTION)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 590
                self.match(EzLangParser.DOTDOTDOT)
                self.state = 591
                self.expression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BlockContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def statement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.StatementContext)
            else:
                return self.getTypedRuleContext(EzLangParser.StatementContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_block

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBlock" ):
                return visitor.visitBlock(self)
            else:
                return visitor.visitChildren(self)




    def block(self):

        localctx = EzLangParser.BlockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 90, self.RULE_block)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 594
            self.match(EzLangParser.LBRACE)
            self.state = 598
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & -4539030290050322434) != 0) or ((((_la - 65)) & ~0x3f) == 0 and ((1 << (_la - 65)) & 245) != 0):
                self.state = 595
                self.statement()
                self.state = 600
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 601
            self.match(EzLangParser.RBRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MatchExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def MATCH(self):
            return self.getToken(EzLangParser.MATCH, 0)

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def matchArm(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MatchArmContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MatchArmContext,i)


        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_matchExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMatchExpr" ):
                return visitor.visitMatchExpr(self)
            else:
                return visitor.visitChildren(self)




    def matchExpr(self):

        localctx = EzLangParser.MatchExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 92, self.RULE_matchExpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 603
            self.match(EzLangParser.MATCH)
            self.state = 604
            self.match(EzLangParser.LBRACE)
            self.state = 605
            self.matchArm()
            self.state = 610
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,60,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 606
                    self.match(EzLangParser.COMMA)
                    self.state = 607
                    self.matchArm() 
                self.state = 612
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,60,self._ctx)

            self.state = 614
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==60:
                self.state = 613
                self.match(EzLangParser.COMMA)


            self.state = 616
            self.match(EzLangParser.RBRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MatchArmContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def QUESTION(self):
            return self.getToken(EzLangParser.QUESTION, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_matchArm

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMatchArm" ):
                return visitor.visitMatchArm(self)
            else:
                return visitor.visitChildren(self)




    def matchArm(self):

        localctx = EzLangParser.MatchArmContext(self, self._ctx, self.state)
        self.enterRule(localctx, 94, self.RULE_matchArm)
        try:
            self.state = 630
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,62,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 618
                self.match(EzLangParser.LPAREN)
                self.state = 619
                self.expression()
                self.state = 620
                self.match(EzLangParser.RPAREN)
                self.state = 621
                self.match(EzLangParser.QUESTION)
                self.state = 622
                self.block()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 624
                self.match(EzLangParser.LPAREN)
                self.state = 625
                self.expression()
                self.state = 626
                self.match(EzLangParser.RPAREN)
                self.state = 627
                self.match(EzLangParser.QUESTION)
                self.state = 628
                self.expression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LoopExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LOOP(self):
            return self.getToken(EzLangParser.LOOP, 0)

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def IN(self):
            return self.getToken(EzLangParser.IN, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def DOTDOTDOT(self):
            return self.getToken(EzLangParser.DOTDOTDOT, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_loopExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLoopExpr" ):
                return visitor.visitLoopExpr(self)
            else:
                return visitor.visitChildren(self)




    def loopExpr(self):

        localctx = EzLangParser.LoopExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 96, self.RULE_loopExpr)
        try:
            self.state = 642
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,63,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 632
                self.match(EzLangParser.LOOP)
                self.state = 633
                self.match(EzLangParser.IDENT)
                self.state = 634
                self.match(EzLangParser.IN)
                self.state = 635
                self.expression()
                self.state = 636
                self.match(EzLangParser.DOTDOTDOT)
                self.state = 637
                self.expression()
                self.state = 638
                self.block()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 640
                self.match(EzLangParser.LOOP)
                self.state = 641
                self.block()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CatchExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CATCH(self):
            return self.getToken(EzLangParser.CATCH, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_catchExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCatchExpr" ):
                return visitor.visitCatchExpr(self)
            else:
                return visitor.visitChildren(self)




    def catchExpr(self):

        localctx = EzLangParser.CatchExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 98, self.RULE_catchExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 644
            self.match(EzLangParser.CATCH)
            self.state = 645
            self.block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArrayLiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACKET(self):
            return self.getToken(EzLangParser.LBRACKET, 0)

        def RBRACKET(self):
            return self.getToken(EzLangParser.RBRACKET, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_arrayLiteral

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArrayLiteral" ):
                return visitor.visitArrayLiteral(self)
            else:
                return visitor.visitChildren(self)




    def arrayLiteral(self):

        localctx = EzLangParser.ArrayLiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 100, self.RULE_arrayLiteral)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 647
            self.match(EzLangParser.LBRACKET)
            self.state = 656
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & -9150716308478393984) != 0) or ((((_la - 65)) & ~0x3f) == 0 and ((1 << (_la - 65)) & 245) != 0):
                self.state = 648
                self.expression()
                self.state = 653
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==60:
                    self.state = 649
                    self.match(EzLangParser.COMMA)
                    self.state = 650
                    self.expression()
                    self.state = 655
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)



            self.state = 658
            self.match(EzLangParser.RBRACKET)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class VecLiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def VEC(self):
            return self.getToken(EzLangParser.VEC, 0)

        def LBRACKET(self):
            return self.getToken(EzLangParser.LBRACKET, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def RBRACKET(self):
            return self.getToken(EzLangParser.RBRACKET, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_vecLiteral

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitVecLiteral" ):
                return visitor.visitVecLiteral(self)
            else:
                return visitor.visitChildren(self)




    def vecLiteral(self):

        localctx = EzLangParser.VecLiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 102, self.RULE_vecLiteral)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 660
            self.match(EzLangParser.VEC)
            self.state = 661
            self.match(EzLangParser.LBRACKET)
            self.state = 662
            self.expression()
            self.state = 667
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==60:
                self.state = 663
                self.match(EzLangParser.COMMA)
                self.state = 664
                self.expression()
                self.state = 669
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 670
            self.match(EzLangParser.RBRACKET)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DictLiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def dictEntry(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.DictEntryContext)
            else:
                return self.getTypedRuleContext(EzLangParser.DictEntryContext,i)


        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_dictLiteral

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDictLiteral" ):
                return visitor.visitDictLiteral(self)
            else:
                return visitor.visitChildren(self)




    def dictLiteral(self):

        localctx = EzLangParser.DictLiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 104, self.RULE_dictLiteral)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 672
            self.match(EzLangParser.LBRACE)
            self.state = 673
            self.dictEntry()
            self.state = 678
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,67,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 674
                    self.match(EzLangParser.COMMA)
                    self.state = 675
                    self.dictEntry() 
                self.state = 680
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,67,self._ctx)

            self.state = 682
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==60:
                self.state = 681
                self.match(EzLangParser.COMMA)


            self.state = 684
            self.match(EzLangParser.RBRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DictEntryContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_dictEntry

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDictEntry" ):
                return visitor.visitDictEntry(self)
            else:
                return visitor.visitChildren(self)




    def dictEntry(self):

        localctx = EzLangParser.DictEntryContext(self, self._ctx, self.state)
        self.enterRule(localctx, 106, self.RULE_dictEntry)
        try:
            self.state = 695
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,69,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 686
                self.match(EzLangParser.IDENT)
                self.state = 687
                self.match(EzLangParser.COLON)
                self.state = 688
                self.typeExpr()
                self.state = 689
                self.match(EzLangParser.ASSIGN)
                self.state = 690
                self.expression()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 692
                self.match(EzLangParser.IDENT)
                self.state = 693
                self.match(EzLangParser.ASSIGN)
                self.state = 694
                self.expression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeofExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def TYPEOF(self):
            return self.getToken(EzLangParser.TYPEOF, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_typeofExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTypeofExpr" ):
                return visitor.visitTypeofExpr(self)
            else:
                return visitor.visitChildren(self)




    def typeofExpr(self):

        localctx = EzLangParser.TypeofExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 108, self.RULE_typeofExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 697
            self.match(EzLangParser.TYPEOF)
            self.state = 698
            self.expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def unionType(self):
            return self.getTypedRuleContext(EzLangParser.UnionTypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_typeExpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTypeExpr" ):
                return visitor.visitTypeExpr(self)
            else:
                return visitor.visitChildren(self)




    def typeExpr(self):

        localctx = EzLangParser.TypeExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 110, self.RULE_typeExpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 700
            self.unionType()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class UnionTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def optionalType(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.OptionalTypeContext)
            else:
                return self.getTypedRuleContext(EzLangParser.OptionalTypeContext,i)


        def BIT_OR(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.BIT_OR)
            else:
                return self.getToken(EzLangParser.BIT_OR, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_unionType

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitUnionType" ):
                return visitor.visitUnionType(self)
            else:
                return visitor.visitChildren(self)




    def unionType(self):

        localctx = EzLangParser.UnionTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 112, self.RULE_unionType)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 702
            self.optionalType()
            self.state = 707
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,70,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 703
                    self.match(EzLangParser.BIT_OR)
                    self.state = 704
                    self.optionalType() 
                self.state = 709
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,70,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class OptionalTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def arrayType(self):
            return self.getTypedRuleContext(EzLangParser.ArrayTypeContext,0)


        def QUESTION(self):
            return self.getToken(EzLangParser.QUESTION, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_optionalType

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitOptionalType" ):
                return visitor.visitOptionalType(self)
            else:
                return visitor.visitChildren(self)




    def optionalType(self):

        localctx = EzLangParser.OptionalTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 114, self.RULE_optionalType)
        try:
            self.state = 714
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,71,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 710
                self.arrayType()
                self.state = 711
                self.match(EzLangParser.QUESTION)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 713
                self.arrayType()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArrayTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def atomicType(self):
            return self.getTypedRuleContext(EzLangParser.AtomicTypeContext,0)


        def LBRACKET(self):
            return self.getToken(EzLangParser.LBRACKET, 0)

        def RBRACKET(self):
            return self.getToken(EzLangParser.RBRACKET, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_arrayType

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArrayType" ):
                return visitor.visitArrayType(self)
            else:
                return visitor.visitChildren(self)




    def arrayType(self):

        localctx = EzLangParser.ArrayTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 116, self.RULE_arrayType)
        try:
            self.state = 721
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,72,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 716
                self.atomicType()
                self.state = 717
                self.match(EzLangParser.LBRACKET)
                self.state = 718
                self.match(EzLangParser.RBRACKET)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 720
                self.atomicType()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AtomicTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def typeArgs(self):
            return self.getTypedRuleContext(EzLangParser.TypeArgsContext,0)


        def VEC(self):
            return self.getToken(EzLangParser.VEC, 0)

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def LBRACKET(self):
            return self.getToken(EzLangParser.LBRACKET, 0)

        def INT_LIT(self):
            return self.getToken(EzLangParser.INT_LIT, 0)

        def RBRACKET(self):
            return self.getToken(EzLangParser.RBRACKET, 0)

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def FAT_ARROW(self):
            return self.getToken(EzLangParser.FAT_ARROW, 0)

        def paramTypeList(self):
            return self.getTypedRuleContext(EzLangParser.ParamTypeListContext,0)


        def STAR(self):
            return self.getToken(EzLangParser.STAR, 0)

        def shapeType(self):
            return self.getTypedRuleContext(EzLangParser.ShapeTypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_atomicType

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAtomicType" ):
                return visitor.visitAtomicType(self)
            else:
                return visitor.visitChildren(self)




    def atomicType(self):

        localctx = EzLangParser.AtomicTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 118, self.RULE_atomicType)
        self._la = 0 # Token type
        try:
            self.state = 745
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [69]:
                self.enterOuterAlt(localctx, 1)
                self.state = 723
                self.match(EzLangParser.IDENT)
                self.state = 725
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,73,self._ctx)
                if la_ == 1:
                    self.state = 724
                    self.typeArgs()


                pass
            elif token in [22]:
                self.enterOuterAlt(localctx, 2)
                self.state = 727
                self.match(EzLangParser.VEC)
                self.state = 728
                self.match(EzLangParser.LT)
                self.state = 729
                self.typeExpr()
                self.state = 730
                self.match(EzLangParser.GT)
                self.state = 731
                self.match(EzLangParser.LBRACKET)
                self.state = 732
                self.match(EzLangParser.INT_LIT)
                self.state = 733
                self.match(EzLangParser.RBRACKET)
                pass
            elif token in [63]:
                self.enterOuterAlt(localctx, 3)
                self.state = 735
                self.match(EzLangParser.LPAREN)
                self.state = 737
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==69:
                    self.state = 736
                    self.paramTypeList()


                self.state = 739
                self.match(EzLangParser.RPAREN)
                self.state = 740
                self.match(EzLangParser.FAT_ARROW)
                self.state = 741
                self.typeExpr()
                pass
            elif token in [50]:
                self.enterOuterAlt(localctx, 4)
                self.state = 742
                self.match(EzLangParser.STAR)
                self.state = 743
                self.match(EzLangParser.IDENT)
                pass
            elif token in [65]:
                self.enterOuterAlt(localctx, 5)
                self.state = 744
                self.shapeType()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParamTypeListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def paramType(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ParamTypeContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ParamTypeContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_paramTypeList

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParamTypeList" ):
                return visitor.visitParamTypeList(self)
            else:
                return visitor.visitChildren(self)




    def paramTypeList(self):

        localctx = EzLangParser.ParamTypeListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 120, self.RULE_paramTypeList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 747
            self.paramType()
            self.state = 752
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==60:
                self.state = 748
                self.match(EzLangParser.COMMA)
                self.state = 749
                self.paramType()
                self.state = 754
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParamTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENT(self):
            return self.getToken(EzLangParser.IDENT, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def typeExpr(self):
            return self.getTypedRuleContext(EzLangParser.TypeExprContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_paramType

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParamType" ):
                return visitor.visitParamType(self)
            else:
                return visitor.visitChildren(self)




    def paramType(self):

        localctx = EzLangParser.ParamTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 122, self.RULE_paramType)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 755
            self.match(EzLangParser.IDENT)
            self.state = 756
            self.match(EzLangParser.COLON)
            self.state = 757
            self.typeExpr()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeParamsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def IDENT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.IDENT)
            else:
                return self.getToken(EzLangParser.IDENT, i)

        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_typeParams

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTypeParams" ):
                return visitor.visitTypeParams(self)
            else:
                return visitor.visitChildren(self)




    def typeParams(self):

        localctx = EzLangParser.TypeParamsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 124, self.RULE_typeParams)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 759
            self.match(EzLangParser.LT)
            self.state = 760
            self.match(EzLangParser.IDENT)
            self.state = 765
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==60:
                self.state = 761
                self.match(EzLangParser.COMMA)
                self.state = 762
                self.match(EzLangParser.IDENT)
                self.state = 767
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 768
            self.match(EzLangParser.GT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeArgsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def typeExpr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.TypeExprContext)
            else:
                return self.getTypedRuleContext(EzLangParser.TypeExprContext,i)


        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_typeArgs

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTypeArgs" ):
                return visitor.visitTypeArgs(self)
            else:
                return visitor.visitChildren(self)




    def typeArgs(self):

        localctx = EzLangParser.TypeArgsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 126, self.RULE_typeArgs)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 770
            self.match(EzLangParser.LT)
            self.state = 771
            self.typeExpr()
            self.state = 776
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==60:
                self.state = 772
                self.match(EzLangParser.COMMA)
                self.state = 773
                self.typeExpr()
                self.state = 778
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 779
            self.match(EzLangParser.GT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





