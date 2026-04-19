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
        4,1,94,753,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,2,22,7,22,2,23,7,23,2,24,7,24,2,25,7,25,2,26,7,26,
        2,27,7,27,2,28,7,28,2,29,7,29,2,30,7,30,2,31,7,31,2,32,7,32,2,33,
        7,33,2,34,7,34,2,35,7,35,2,36,7,36,2,37,7,37,2,38,7,38,2,39,7,39,
        2,40,7,40,2,41,7,41,2,42,7,42,2,43,7,43,2,44,7,44,2,45,7,45,2,46,
        7,46,2,47,7,47,2,48,7,48,2,49,7,49,2,50,7,50,2,51,7,51,2,52,7,52,
        2,53,7,53,2,54,7,54,2,55,7,55,2,56,7,56,2,57,7,57,2,58,7,58,2,59,
        7,59,2,60,7,60,2,61,7,61,2,62,7,62,2,63,7,63,2,64,7,64,2,65,7,65,
        2,66,7,66,2,67,7,67,2,68,7,68,2,69,7,69,2,70,7,70,2,71,7,71,2,72,
        7,72,1,0,5,0,148,8,0,10,0,12,0,151,9,0,1,0,1,0,1,1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,1,3,1,164,8,1,1,2,1,2,1,2,3,2,169,8,2,1,2,1,2,1,
        2,1,2,1,3,3,3,176,8,3,1,3,1,3,1,3,3,3,181,8,3,1,3,1,3,3,3,185,8,
        3,1,3,1,3,1,3,1,3,1,4,1,4,1,4,3,4,194,8,4,1,4,1,4,1,4,1,4,1,4,1,
        5,1,5,1,5,5,5,204,8,5,10,5,12,5,207,9,5,1,6,1,6,1,6,1,6,1,7,1,7,
        1,7,1,7,1,7,3,7,218,8,7,1,7,1,7,1,8,1,8,1,8,1,8,1,8,1,9,3,9,228,
        8,9,1,9,1,9,1,9,1,9,1,9,1,9,1,10,1,10,3,10,238,8,10,1,10,1,10,1,
        10,3,10,243,8,10,1,10,1,10,1,11,1,11,1,11,5,11,250,8,11,10,11,12,
        11,253,9,11,1,12,1,12,3,12,257,8,12,1,12,1,12,1,12,1,12,3,12,263,
        8,12,1,13,1,13,1,13,3,13,268,8,13,1,14,1,14,5,14,272,8,14,10,14,
        12,14,275,9,14,1,14,1,14,1,15,1,15,1,16,1,16,1,16,1,16,1,16,1,16,
        1,16,1,16,1,17,1,17,1,17,5,17,292,8,17,10,17,12,17,295,9,17,1,18,
        1,18,1,18,3,18,300,8,18,1,19,1,19,1,19,1,19,1,19,3,19,307,8,19,1,
        20,1,20,3,20,311,8,20,1,20,1,20,1,20,1,20,1,20,1,21,1,21,1,22,1,
        22,1,22,1,22,1,22,3,22,325,8,22,1,22,5,22,328,8,22,10,22,12,22,331,
        9,22,1,23,1,23,1,23,1,23,5,23,337,8,23,10,23,12,23,340,9,23,1,24,
        1,24,1,25,1,25,1,25,1,25,1,25,1,25,3,25,350,8,25,1,26,1,26,1,26,
        5,26,355,8,26,10,26,12,26,358,9,26,1,27,1,27,1,27,5,27,363,8,27,
        10,27,12,27,366,9,27,1,28,1,28,1,28,1,28,5,28,372,8,28,10,28,12,
        28,375,9,28,1,29,1,29,1,30,1,30,1,30,1,30,5,30,383,8,30,10,30,12,
        30,386,9,30,1,31,1,31,1,32,1,32,1,32,1,32,5,32,394,8,32,10,32,12,
        32,397,9,32,1,33,1,33,1,34,1,34,1,34,1,34,5,34,405,8,34,10,34,12,
        34,408,9,34,1,35,1,35,1,36,1,36,1,36,1,36,5,36,416,8,36,10,36,12,
        36,419,9,36,1,37,1,37,1,38,1,38,1,38,3,38,426,8,38,1,39,1,39,5,39,
        430,8,39,10,39,12,39,433,9,39,1,40,1,40,1,40,1,40,3,40,439,8,40,
        1,40,1,40,1,40,1,40,1,40,1,40,3,40,447,8,40,1,41,1,41,1,41,5,41,
        452,8,41,10,41,12,41,455,9,41,1,42,1,42,1,42,1,42,3,42,461,8,42,
        1,43,1,43,1,43,1,43,1,43,1,43,1,43,1,43,1,43,1,43,1,43,1,43,1,43,
        1,43,1,43,1,43,1,43,1,43,1,43,1,43,3,43,483,8,43,1,44,1,44,1,45,
        1,45,1,45,1,45,1,45,3,45,492,8,45,1,45,1,45,1,45,1,45,5,45,498,8,
        45,10,45,12,45,501,9,45,1,45,1,45,1,45,1,45,1,45,1,45,1,45,5,45,
        510,8,45,10,45,12,45,513,9,45,1,45,1,45,3,45,517,8,45,1,46,1,46,
        3,46,521,8,46,1,46,1,46,3,46,525,8,46,1,46,1,46,1,47,1,47,1,47,5,
        47,532,8,47,10,47,12,47,535,9,47,1,48,1,48,1,48,1,48,1,48,3,48,542,
        8,48,1,49,1,49,1,49,3,49,547,8,49,1,49,1,49,1,49,3,49,552,8,49,1,
        49,1,49,1,49,1,49,1,49,1,49,1,49,3,49,561,8,49,1,49,1,49,3,49,565,
        8,49,1,50,4,50,568,8,50,11,50,12,50,569,1,51,1,51,1,51,1,51,1,51,
        1,51,3,51,578,8,51,1,52,1,52,1,52,1,52,1,52,1,52,5,52,586,8,52,10,
        52,12,52,589,9,52,1,53,1,53,1,53,1,53,1,53,1,53,5,53,597,8,53,10,
        53,12,53,600,9,53,1,53,1,53,1,54,1,54,1,54,1,55,1,55,1,55,5,55,610,
        8,55,10,55,12,55,613,9,55,1,56,1,56,5,56,617,8,56,10,56,12,56,620,
        9,56,1,57,1,57,3,57,624,8,57,1,57,1,57,1,57,1,57,1,57,1,57,5,57,
        632,8,57,10,57,12,57,635,9,57,1,57,1,57,1,57,1,57,3,57,641,8,57,
        1,57,1,57,1,57,1,57,1,57,1,57,1,57,1,57,1,57,1,57,1,57,3,57,654,
        8,57,1,58,1,58,1,59,1,59,1,59,1,60,1,60,1,60,1,60,1,61,1,61,3,61,
        667,8,61,1,61,1,61,1,61,1,61,1,62,1,62,1,62,1,63,1,63,1,63,1,63,
        5,63,680,8,63,10,63,12,63,683,9,63,1,63,1,63,1,64,1,64,1,64,1,64,
        5,64,691,8,64,10,64,12,64,694,9,64,1,64,1,64,1,65,1,65,1,65,1,66,
        1,66,1,66,3,66,704,8,66,1,67,1,67,1,67,3,67,709,8,67,1,68,1,68,1,
        69,1,69,1,69,1,69,1,69,1,69,1,69,1,70,1,70,1,70,1,70,3,70,724,8,
        70,1,70,1,70,1,70,3,70,729,8,70,3,70,731,8,70,1,71,1,71,1,71,1,71,
        1,71,5,71,738,8,71,10,71,12,71,741,9,71,1,71,1,71,1,72,1,72,1,72,
        1,72,1,72,1,72,3,72,751,8,72,1,72,0,0,73,0,2,4,6,8,10,12,14,16,18,
        20,22,24,26,28,30,32,34,36,38,40,42,44,46,48,50,52,54,56,58,60,62,
        64,66,68,70,72,74,76,78,80,82,84,86,88,90,92,94,96,98,100,102,104,
        106,108,110,112,114,116,118,120,122,124,126,128,130,132,134,136,
        138,140,142,144,0,10,1,0,27,29,2,0,1,10,71,71,1,0,65,66,1,0,67,70,
        1,0,60,61,1,0,52,53,1,0,54,56,3,0,11,11,52,53,64,64,2,0,47,48,88,
        90,2,0,16,26,87,87,778,0,149,1,0,0,0,2,163,1,0,0,0,4,165,1,0,0,0,
        6,175,1,0,0,0,8,190,1,0,0,0,10,205,1,0,0,0,12,208,1,0,0,0,14,212,
        1,0,0,0,16,221,1,0,0,0,18,227,1,0,0,0,20,235,1,0,0,0,22,246,1,0,
        0,0,24,254,1,0,0,0,26,267,1,0,0,0,28,269,1,0,0,0,30,278,1,0,0,0,
        32,280,1,0,0,0,34,288,1,0,0,0,36,296,1,0,0,0,38,301,1,0,0,0,40,308,
        1,0,0,0,42,317,1,0,0,0,44,319,1,0,0,0,46,332,1,0,0,0,48,341,1,0,
        0,0,50,343,1,0,0,0,52,351,1,0,0,0,54,359,1,0,0,0,56,367,1,0,0,0,
        58,376,1,0,0,0,60,378,1,0,0,0,62,387,1,0,0,0,64,389,1,0,0,0,66,398,
        1,0,0,0,68,400,1,0,0,0,70,409,1,0,0,0,72,411,1,0,0,0,74,420,1,0,
        0,0,76,425,1,0,0,0,78,427,1,0,0,0,80,446,1,0,0,0,82,448,1,0,0,0,
        84,460,1,0,0,0,86,482,1,0,0,0,88,484,1,0,0,0,90,516,1,0,0,0,92,518,
        1,0,0,0,94,528,1,0,0,0,96,541,1,0,0,0,98,564,1,0,0,0,100,567,1,0,
        0,0,102,577,1,0,0,0,104,587,1,0,0,0,106,590,1,0,0,0,108,603,1,0,
        0,0,110,606,1,0,0,0,112,614,1,0,0,0,114,653,1,0,0,0,116,655,1,0,
        0,0,118,657,1,0,0,0,120,660,1,0,0,0,122,664,1,0,0,0,124,672,1,0,
        0,0,126,675,1,0,0,0,128,686,1,0,0,0,130,697,1,0,0,0,132,703,1,0,
        0,0,134,705,1,0,0,0,136,710,1,0,0,0,138,712,1,0,0,0,140,719,1,0,
        0,0,142,732,1,0,0,0,144,744,1,0,0,0,146,148,3,2,1,0,147,146,1,0,
        0,0,148,151,1,0,0,0,149,147,1,0,0,0,149,150,1,0,0,0,150,152,1,0,
        0,0,151,149,1,0,0,0,152,153,5,0,0,1,153,1,1,0,0,0,154,164,3,4,2,
        0,155,164,3,6,3,0,156,164,3,8,4,0,157,164,3,18,9,0,158,164,3,32,
        16,0,159,164,3,38,19,0,160,164,3,40,20,0,161,164,3,108,54,0,162,
        164,3,30,15,0,163,154,1,0,0,0,163,155,1,0,0,0,163,156,1,0,0,0,163,
        157,1,0,0,0,163,158,1,0,0,0,163,159,1,0,0,0,163,160,1,0,0,0,163,
        161,1,0,0,0,163,162,1,0,0,0,164,3,1,0,0,0,165,166,5,31,0,0,166,168,
        5,87,0,0,167,169,3,128,64,0,168,167,1,0,0,0,168,169,1,0,0,0,169,
        170,1,0,0,0,170,171,5,71,0,0,171,172,3,110,55,0,172,173,5,74,0,0,
        173,5,1,0,0,0,174,176,3,130,65,0,175,174,1,0,0,0,175,176,1,0,0,0,
        176,177,1,0,0,0,177,178,7,0,0,0,178,180,5,87,0,0,179,181,3,128,64,
        0,180,179,1,0,0,0,180,181,1,0,0,0,181,184,1,0,0,0,182,183,5,73,0,
        0,183,185,3,110,55,0,184,182,1,0,0,0,184,185,1,0,0,0,185,186,1,0,
        0,0,186,187,5,71,0,0,187,188,3,42,21,0,188,189,5,74,0,0,189,7,1,
        0,0,0,190,191,5,30,0,0,191,193,5,87,0,0,192,194,3,128,64,0,193,192,
        1,0,0,0,193,194,1,0,0,0,194,195,1,0,0,0,195,196,5,81,0,0,196,197,
        3,10,5,0,197,198,5,82,0,0,198,199,5,74,0,0,199,9,1,0,0,0,200,204,
        3,12,6,0,201,204,3,14,7,0,202,204,3,16,8,0,203,200,1,0,0,0,203,201,
        1,0,0,0,203,202,1,0,0,0,204,207,1,0,0,0,205,203,1,0,0,0,205,206,
        1,0,0,0,206,11,1,0,0,0,207,205,1,0,0,0,208,209,5,86,0,0,209,210,
        5,87,0,0,210,211,5,74,0,0,211,13,1,0,0,0,212,213,5,87,0,0,213,214,
        5,73,0,0,214,217,3,110,55,0,215,216,5,71,0,0,216,218,3,42,21,0,217,
        215,1,0,0,0,217,218,1,0,0,0,218,219,1,0,0,0,219,220,5,74,0,0,220,
        15,1,0,0,0,221,222,5,87,0,0,222,223,5,71,0,0,223,224,3,20,10,0,224,
        225,5,74,0,0,225,17,1,0,0,0,226,228,5,35,0,0,227,226,1,0,0,0,227,
        228,1,0,0,0,228,229,1,0,0,0,229,230,5,28,0,0,230,231,5,87,0,0,231,
        232,5,71,0,0,232,233,3,20,10,0,233,234,5,74,0,0,234,19,1,0,0,0,235,
        237,5,77,0,0,236,238,3,22,11,0,237,236,1,0,0,0,237,238,1,0,0,0,238,
        239,1,0,0,0,239,242,5,78,0,0,240,241,5,84,0,0,241,243,3,110,55,0,
        242,240,1,0,0,0,242,243,1,0,0,0,243,244,1,0,0,0,244,245,3,26,13,
        0,245,21,1,0,0,0,246,251,3,24,12,0,247,248,5,75,0,0,248,250,3,24,
        12,0,249,247,1,0,0,0,250,253,1,0,0,0,251,249,1,0,0,0,251,252,1,0,
        0,0,252,23,1,0,0,0,253,251,1,0,0,0,254,256,5,87,0,0,255,257,5,72,
        0,0,256,255,1,0,0,0,256,257,1,0,0,0,257,258,1,0,0,0,258,259,5,73,
        0,0,259,262,3,110,55,0,260,261,5,71,0,0,261,263,3,42,21,0,262,260,
        1,0,0,0,262,263,1,0,0,0,263,25,1,0,0,0,264,268,3,28,14,0,265,266,
        5,84,0,0,266,268,3,42,21,0,267,264,1,0,0,0,267,265,1,0,0,0,268,27,
        1,0,0,0,269,273,5,81,0,0,270,272,3,2,1,0,271,270,1,0,0,0,272,275,
        1,0,0,0,273,271,1,0,0,0,273,274,1,0,0,0,274,276,1,0,0,0,275,273,
        1,0,0,0,276,277,5,82,0,0,277,29,1,0,0,0,278,279,3,28,14,0,279,31,
        1,0,0,0,280,281,5,40,0,0,281,282,5,90,0,0,282,283,5,38,0,0,283,284,
        5,81,0,0,284,285,3,34,17,0,285,286,5,82,0,0,286,287,5,74,0,0,287,
        33,1,0,0,0,288,293,3,36,18,0,289,290,5,75,0,0,290,292,3,36,18,0,
        291,289,1,0,0,0,292,295,1,0,0,0,293,291,1,0,0,0,293,294,1,0,0,0,
        294,35,1,0,0,0,295,293,1,0,0,0,296,299,5,87,0,0,297,298,5,50,0,0,
        298,300,5,87,0,0,299,297,1,0,0,0,299,300,1,0,0,0,300,37,1,0,0,0,
        301,306,5,39,0,0,302,307,3,6,3,0,303,307,3,8,4,0,304,307,3,18,9,
        0,305,307,3,4,2,0,306,302,1,0,0,0,306,303,1,0,0,0,306,304,1,0,0,
        0,306,305,1,0,0,0,307,39,1,0,0,0,308,310,5,32,0,0,309,311,7,0,0,
        0,310,309,1,0,0,0,310,311,1,0,0,0,311,312,1,0,0,0,312,313,5,87,0,
        0,313,314,5,73,0,0,314,315,3,110,55,0,315,316,5,74,0,0,316,41,1,
        0,0,0,317,318,3,44,22,0,318,43,1,0,0,0,319,329,3,50,25,0,320,321,
        5,85,0,0,321,322,5,87,0,0,322,324,5,77,0,0,323,325,3,82,41,0,324,
        323,1,0,0,0,324,325,1,0,0,0,325,326,1,0,0,0,326,328,5,78,0,0,327,
        320,1,0,0,0,328,331,1,0,0,0,329,327,1,0,0,0,329,330,1,0,0,0,330,
        45,1,0,0,0,331,329,1,0,0,0,332,338,3,50,25,0,333,334,3,48,24,0,334,
        335,3,50,25,0,335,337,1,0,0,0,336,333,1,0,0,0,337,340,1,0,0,0,338,
        336,1,0,0,0,338,339,1,0,0,0,339,47,1,0,0,0,340,338,1,0,0,0,341,342,
        7,1,0,0,342,49,1,0,0,0,343,349,3,52,26,0,344,345,5,72,0,0,345,346,
        3,42,21,0,346,347,5,73,0,0,347,348,3,42,21,0,348,350,1,0,0,0,349,
        344,1,0,0,0,349,350,1,0,0,0,350,51,1,0,0,0,351,356,3,54,27,0,352,
        353,5,63,0,0,353,355,3,54,27,0,354,352,1,0,0,0,355,358,1,0,0,0,356,
        354,1,0,0,0,356,357,1,0,0,0,357,53,1,0,0,0,358,356,1,0,0,0,359,364,
        3,56,28,0,360,361,5,62,0,0,361,363,3,56,28,0,362,360,1,0,0,0,363,
        366,1,0,0,0,364,362,1,0,0,0,364,365,1,0,0,0,365,55,1,0,0,0,366,364,
        1,0,0,0,367,373,3,60,30,0,368,369,3,58,29,0,369,370,3,60,30,0,370,
        372,1,0,0,0,371,368,1,0,0,0,372,375,1,0,0,0,373,371,1,0,0,0,373,
        374,1,0,0,0,374,57,1,0,0,0,375,373,1,0,0,0,376,377,7,2,0,0,377,59,
        1,0,0,0,378,384,3,64,32,0,379,380,3,62,31,0,380,381,3,64,32,0,381,
        383,1,0,0,0,382,379,1,0,0,0,383,386,1,0,0,0,384,382,1,0,0,0,384,
        385,1,0,0,0,385,61,1,0,0,0,386,384,1,0,0,0,387,388,7,3,0,0,388,63,
        1,0,0,0,389,395,3,68,34,0,390,391,3,66,33,0,391,392,3,68,34,0,392,
        394,1,0,0,0,393,390,1,0,0,0,394,397,1,0,0,0,395,393,1,0,0,0,395,
        396,1,0,0,0,396,65,1,0,0,0,397,395,1,0,0,0,398,399,7,4,0,0,399,67,
        1,0,0,0,400,406,3,72,36,0,401,402,3,70,35,0,402,403,3,72,36,0,403,
        405,1,0,0,0,404,401,1,0,0,0,405,408,1,0,0,0,406,404,1,0,0,0,406,
        407,1,0,0,0,407,69,1,0,0,0,408,406,1,0,0,0,409,410,7,5,0,0,410,71,
        1,0,0,0,411,417,3,76,38,0,412,413,3,74,37,0,413,414,3,76,38,0,414,
        416,1,0,0,0,415,412,1,0,0,0,416,419,1,0,0,0,417,415,1,0,0,0,417,
        418,1,0,0,0,418,73,1,0,0,0,419,417,1,0,0,0,420,421,7,6,0,0,421,75,
        1,0,0,0,422,423,7,7,0,0,423,426,3,76,38,0,424,426,3,78,39,0,425,
        422,1,0,0,0,425,424,1,0,0,0,426,77,1,0,0,0,427,431,3,86,43,0,428,
        430,3,80,40,0,429,428,1,0,0,0,430,433,1,0,0,0,431,429,1,0,0,0,431,
        432,1,0,0,0,432,79,1,0,0,0,433,431,1,0,0,0,434,435,5,76,0,0,435,
        447,5,87,0,0,436,438,5,77,0,0,437,439,3,82,41,0,438,437,1,0,0,0,
        438,439,1,0,0,0,439,440,1,0,0,0,440,447,5,78,0,0,441,442,5,79,0,
        0,442,443,3,42,21,0,443,444,5,80,0,0,444,447,1,0,0,0,445,447,5,64,
        0,0,446,434,1,0,0,0,446,436,1,0,0,0,446,441,1,0,0,0,446,445,1,0,
        0,0,447,81,1,0,0,0,448,453,3,84,42,0,449,450,5,75,0,0,450,452,3,
        84,42,0,451,449,1,0,0,0,452,455,1,0,0,0,453,451,1,0,0,0,453,454,
        1,0,0,0,454,83,1,0,0,0,455,453,1,0,0,0,456,457,5,87,0,0,457,458,
        5,71,0,0,458,461,3,42,21,0,459,461,3,42,21,0,460,456,1,0,0,0,460,
        459,1,0,0,0,461,85,1,0,0,0,462,483,3,88,44,0,463,483,5,87,0,0,464,
        465,5,77,0,0,465,466,3,42,21,0,466,467,5,78,0,0,467,483,1,0,0,0,
        468,483,3,90,45,0,469,483,3,92,46,0,470,483,3,98,49,0,471,472,5,
        44,0,0,472,473,5,77,0,0,473,474,3,42,21,0,474,475,5,78,0,0,475,483,
        1,0,0,0,476,477,5,42,0,0,477,483,3,28,14,0,478,479,5,43,0,0,479,
        483,3,42,21,0,480,481,5,34,0,0,481,483,3,42,21,0,482,462,1,0,0,0,
        482,463,1,0,0,0,482,464,1,0,0,0,482,468,1,0,0,0,482,469,1,0,0,0,
        482,470,1,0,0,0,482,471,1,0,0,0,482,476,1,0,0,0,482,478,1,0,0,0,
        482,480,1,0,0,0,483,87,1,0,0,0,484,485,7,8,0,0,485,89,1,0,0,0,486,
        491,5,12,0,0,487,488,5,67,0,0,488,489,3,112,56,0,489,490,5,68,0,
        0,490,492,1,0,0,0,491,487,1,0,0,0,491,492,1,0,0,0,492,493,1,0,0,
        0,493,494,5,79,0,0,494,499,3,42,21,0,495,496,5,75,0,0,496,498,3,
        42,21,0,497,495,1,0,0,0,498,501,1,0,0,0,499,497,1,0,0,0,499,500,
        1,0,0,0,500,502,1,0,0,0,501,499,1,0,0,0,502,503,5,80,0,0,503,517,
        1,0,0,0,504,505,5,12,0,0,505,506,5,79,0,0,506,511,3,42,21,0,507,
        508,5,75,0,0,508,510,3,42,21,0,509,507,1,0,0,0,510,513,1,0,0,0,511,
        509,1,0,0,0,511,512,1,0,0,0,512,514,1,0,0,0,513,511,1,0,0,0,514,
        515,5,80,0,0,515,517,1,0,0,0,516,486,1,0,0,0,516,504,1,0,0,0,517,
        91,1,0,0,0,518,520,5,87,0,0,519,521,3,126,63,0,520,519,1,0,0,0,520,
        521,1,0,0,0,521,522,1,0,0,0,522,524,5,77,0,0,523,525,3,94,47,0,524,
        523,1,0,0,0,524,525,1,0,0,0,525,526,1,0,0,0,526,527,5,78,0,0,527,
        93,1,0,0,0,528,533,3,96,48,0,529,530,5,75,0,0,530,532,3,96,48,0,
        531,529,1,0,0,0,532,535,1,0,0,0,533,531,1,0,0,0,533,534,1,0,0,0,
        534,95,1,0,0,0,535,533,1,0,0,0,536,537,5,87,0,0,537,538,5,71,0,0,
        538,542,3,42,21,0,539,540,5,86,0,0,540,542,3,42,21,0,541,536,1,0,
        0,0,541,539,1,0,0,0,542,97,1,0,0,0,543,544,5,67,0,0,544,546,5,87,
        0,0,545,547,3,100,50,0,546,545,1,0,0,0,546,547,1,0,0,0,547,548,1,
        0,0,0,548,551,5,68,0,0,549,552,3,104,52,0,550,552,5,55,0,0,551,549,
        1,0,0,0,551,550,1,0,0,0,552,553,1,0,0,0,553,554,5,67,0,0,554,555,
        5,55,0,0,555,556,5,87,0,0,556,565,5,68,0,0,557,558,5,67,0,0,558,
        560,5,87,0,0,559,561,3,100,50,0,560,559,1,0,0,0,560,561,1,0,0,0,
        561,562,1,0,0,0,562,563,5,55,0,0,563,565,5,68,0,0,564,543,1,0,0,
        0,564,557,1,0,0,0,565,99,1,0,0,0,566,568,3,102,51,0,567,566,1,0,
        0,0,568,569,1,0,0,0,569,567,1,0,0,0,569,570,1,0,0,0,570,101,1,0,
        0,0,571,572,5,87,0,0,572,573,5,71,0,0,573,578,5,90,0,0,574,575,5,
        87,0,0,575,576,5,71,0,0,576,578,3,42,21,0,577,571,1,0,0,0,577,574,
        1,0,0,0,578,103,1,0,0,0,579,586,5,90,0,0,580,581,5,81,0,0,581,582,
        3,42,21,0,582,583,5,82,0,0,583,586,1,0,0,0,584,586,3,98,49,0,585,
        579,1,0,0,0,585,580,1,0,0,0,585,584,1,0,0,0,586,589,1,0,0,0,587,
        585,1,0,0,0,587,588,1,0,0,0,588,105,1,0,0,0,589,587,1,0,0,0,590,
        598,5,13,0,0,591,597,5,94,0,0,592,593,5,14,0,0,593,594,3,42,21,0,
        594,595,5,15,0,0,595,597,1,0,0,0,596,591,1,0,0,0,596,592,1,0,0,0,
        597,600,1,0,0,0,598,596,1,0,0,0,598,599,1,0,0,0,599,601,1,0,0,0,
        600,598,1,0,0,0,601,602,5,13,0,0,602,107,1,0,0,0,603,604,3,42,21,
        0,604,605,5,74,0,0,605,109,1,0,0,0,606,611,3,112,56,0,607,608,5,
        58,0,0,608,610,3,112,56,0,609,607,1,0,0,0,610,613,1,0,0,0,611,609,
        1,0,0,0,611,612,1,0,0,0,612,111,1,0,0,0,613,611,1,0,0,0,614,618,
        3,116,58,0,615,617,3,114,57,0,616,615,1,0,0,0,617,620,1,0,0,0,618,
        616,1,0,0,0,618,619,1,0,0,0,619,113,1,0,0,0,620,618,1,0,0,0,621,
        623,5,79,0,0,622,624,5,88,0,0,623,622,1,0,0,0,623,624,1,0,0,0,624,
        625,1,0,0,0,625,654,5,80,0,0,626,654,5,72,0,0,627,628,5,67,0,0,628,
        633,3,112,56,0,629,630,5,75,0,0,630,632,3,112,56,0,631,629,1,0,0,
        0,632,635,1,0,0,0,633,631,1,0,0,0,633,634,1,0,0,0,634,636,1,0,0,
        0,635,633,1,0,0,0,636,637,5,68,0,0,637,654,1,0,0,0,638,640,5,77,
        0,0,639,641,3,22,11,0,640,639,1,0,0,0,640,641,1,0,0,0,641,642,1,
        0,0,0,642,643,5,78,0,0,643,644,5,84,0,0,644,654,3,112,56,0,645,646,
        5,12,0,0,646,647,5,67,0,0,647,648,3,112,56,0,648,649,5,68,0,0,649,
        650,5,79,0,0,650,651,5,88,0,0,651,652,5,80,0,0,652,654,1,0,0,0,653,
        621,1,0,0,0,653,626,1,0,0,0,653,627,1,0,0,0,653,638,1,0,0,0,653,
        645,1,0,0,0,654,115,1,0,0,0,655,656,7,9,0,0,656,117,1,0,0,0,657,
        658,3,110,55,0,658,659,5,72,0,0,659,119,1,0,0,0,660,661,3,110,55,
        0,661,662,5,58,0,0,662,663,3,110,55,0,663,121,1,0,0,0,664,666,5,
        77,0,0,665,667,3,22,11,0,666,665,1,0,0,0,666,667,1,0,0,0,667,668,
        1,0,0,0,668,669,5,78,0,0,669,670,5,84,0,0,670,671,3,110,55,0,671,
        123,1,0,0,0,672,673,5,87,0,0,673,674,3,126,63,0,674,125,1,0,0,0,
        675,676,5,67,0,0,676,681,3,112,56,0,677,678,5,75,0,0,678,680,3,112,
        56,0,679,677,1,0,0,0,680,683,1,0,0,0,681,679,1,0,0,0,681,682,1,0,
        0,0,682,684,1,0,0,0,683,681,1,0,0,0,684,685,5,68,0,0,685,127,1,0,
        0,0,686,687,5,67,0,0,687,692,5,87,0,0,688,689,5,75,0,0,689,691,5,
        87,0,0,690,688,1,0,0,0,691,694,1,0,0,0,692,690,1,0,0,0,692,693,1,
        0,0,0,693,695,1,0,0,0,694,692,1,0,0,0,695,696,5,68,0,0,696,129,1,
        0,0,0,697,698,5,83,0,0,698,699,5,87,0,0,699,131,1,0,0,0,700,704,
        3,134,67,0,701,704,3,142,71,0,702,704,3,140,70,0,703,700,1,0,0,0,
        703,701,1,0,0,0,703,702,1,0,0,0,704,133,1,0,0,0,705,708,5,33,0,0,
        706,709,3,138,69,0,707,709,3,136,68,0,708,706,1,0,0,0,708,707,1,
        0,0,0,709,135,1,0,0,0,710,711,3,28,14,0,711,137,1,0,0,0,712,713,
        5,87,0,0,713,714,5,51,0,0,714,715,3,42,21,0,715,716,5,86,0,0,716,
        717,3,42,21,0,717,718,3,28,14,0,718,139,1,0,0,0,719,720,3,42,21,
        0,720,723,5,72,0,0,721,724,3,42,21,0,722,724,3,28,14,0,723,721,1,
        0,0,0,723,722,1,0,0,0,724,730,1,0,0,0,725,728,5,73,0,0,726,729,3,
        42,21,0,727,729,3,28,14,0,728,726,1,0,0,0,728,727,1,0,0,0,729,731,
        1,0,0,0,730,725,1,0,0,0,730,731,1,0,0,0,731,141,1,0,0,0,732,733,
        5,41,0,0,733,734,5,81,0,0,734,739,3,144,72,0,735,736,5,75,0,0,736,
        738,3,144,72,0,737,735,1,0,0,0,738,741,1,0,0,0,739,737,1,0,0,0,739,
        740,1,0,0,0,740,742,1,0,0,0,741,739,1,0,0,0,742,743,5,82,0,0,743,
        143,1,0,0,0,744,745,5,77,0,0,745,746,3,42,21,0,746,747,5,78,0,0,
        747,750,5,72,0,0,748,751,3,42,21,0,749,751,3,28,14,0,750,748,1,0,
        0,0,750,749,1,0,0,0,751,145,1,0,0,0,74,149,163,168,175,180,184,193,
        203,205,217,227,237,242,251,256,262,267,273,293,299,306,310,324,
        329,338,349,356,364,373,384,395,406,417,425,431,438,446,453,460,
        482,491,499,511,516,520,524,533,541,546,551,560,564,569,577,585,
        587,596,598,611,618,623,633,640,653,666,681,692,703,708,723,728,
        730,739,750
    ]

class EzLangParser ( Parser ):

    grammarFileName = "EzLang.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'+='", "'-='", "'*='", "'/='", "'%='", 
                     "'&='", "'|='", "'^='", "'<<='", "'>>='", "'~'", "'Vec'", 
                     "'\"'", "'{{'", "'}}'", "'I8'", "'I32'", "'I64'", "'U8'", 
                     "'U32'", "'U64'", "'F32'", "'F64'", "'Str'", "'Bool'", 
                     "'Void'", "'let'", "'const'", "'static'", "'struct'", 
                     "'type'", "'declare'", "'loop'", "'await'", "'async'", 
                     "'break'", "'continue'", "'import'", "'export'", "'from'", 
                     "'match'", "'catch'", "'throw'", "'typeof'", "'fn'", 
                     "'this'", "'true'", "'false'", "'void'", "'as'", "'in'", 
                     "'+'", "'-'", "'*'", "'/'", "'%'", "'&'", "'|'", "'^'", 
                     "'<<'", "'>>'", "'&&'", "'||'", "'!'", "'=='", "'!='", 
                     "'<'", "'>'", "'<='", "'>='", "'='", "'?'", "':'", 
                     "';'", "','", "'.'", "'('", "')'", "'['", "']'", "'{'", 
                     "'}'", "'@'", "'=>'", "'->'", "'...'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "LET", "CONST", 
                      "STATIC", "STRUCT", "TYPE", "DECLARE", "LOOP", "AWAIT", 
                      "ASYNC", "BREAK", "CONTINUE", "IMPORT", "EXPORT", 
                      "FROM", "MATCH", "CATCH", "THROW", "TYPEOF", "FN", 
                      "THIS", "TRUE", "FALSE", "VOID", "AS", "IN", "PLUS", 
                      "MINUS", "MUL", "DIV", "MOD", "AND", "OR", "XOR", 
                      "LSHIFT", "RSHIFT", "LAND", "LOR", "NOT", "EQ", "NE", 
                      "LT", "GT", "LE", "GE", "ASSIGN", "QMARK", "COLON", 
                      "SEMI", "COMMA", "DOT", "LPAREN", "RPAREN", "LBRACK", 
                      "RBRACK", "LBRACE", "RBRACE", "AT", "ARROW", "PIPE", 
                      "ELLIPSIS", "ID", "INT", "FLOAT", "STRING", "LINE_COMMENT", 
                      "BLOCK_COMMENT", "WS", "STRING_CONTENT" ]

    RULE_program = 0
    RULE_statement = 1
    RULE_typeDeclaration = 2
    RULE_variableDeclaration = 3
    RULE_structDeclaration = 4
    RULE_structBody = 5
    RULE_baseStruct = 6
    RULE_field = 7
    RULE_method = 8
    RULE_functionDeclaration = 9
    RULE_functionExpression = 10
    RULE_parameters = 11
    RULE_parameter = 12
    RULE_blockOrExpression = 13
    RULE_block = 14
    RULE_blockStatement = 15
    RULE_importStatement = 16
    RULE_importItems = 17
    RULE_importItem = 18
    RULE_exportStatement = 19
    RULE_declareStatement = 20
    RULE_expression = 21
    RULE_pipelineExpression = 22
    RULE_assignmentExpression = 23
    RULE_assignmentOp = 24
    RULE_conditionalExpression = 25
    RULE_logicalOrExpression = 26
    RULE_logicalAndExpression = 27
    RULE_equalityExpression = 28
    RULE_equalityOp = 29
    RULE_relationalExpression = 30
    RULE_relationalOp = 31
    RULE_shiftExpression = 32
    RULE_shiftOp = 33
    RULE_additiveExpression = 34
    RULE_addOp = 35
    RULE_multiplicativeExpression = 36
    RULE_mulOp = 37
    RULE_unaryExpression = 38
    RULE_postfixExpression = 39
    RULE_postfix = 40
    RULE_argumentList = 41
    RULE_namedArgument = 42
    RULE_primaryExpression = 43
    RULE_literal = 44
    RULE_vectorLiteral = 45
    RULE_structLiteral = 46
    RULE_structFields = 47
    RULE_structField = 48
    RULE_markupLiteral = 49
    RULE_markupAttrs = 50
    RULE_markupAttr = 51
    RULE_markupContent = 52
    RULE_interpolatedString = 53
    RULE_expressionStatement = 54
    RULE_type = 55
    RULE_simpleType = 56
    RULE_typeSuffix = 57
    RULE_baseType = 58
    RULE_optionalType = 59
    RULE_unionType = 60
    RULE_functionType = 61
    RULE_genericType = 62
    RULE_genericArgs = 63
    RULE_genericParams = 64
    RULE_decorator = 65
    RULE_controlStatement = 66
    RULE_loopStatement = 67
    RULE_infiniteLoop = 68
    RULE_rangeLoop = 69
    RULE_conditionalStatement = 70
    RULE_matchStatement = 71
    RULE_matchCase = 72

    ruleNames =  [ "program", "statement", "typeDeclaration", "variableDeclaration", 
                   "structDeclaration", "structBody", "baseStruct", "field", 
                   "method", "functionDeclaration", "functionExpression", 
                   "parameters", "parameter", "blockOrExpression", "block", 
                   "blockStatement", "importStatement", "importItems", "importItem", 
                   "exportStatement", "declareStatement", "expression", 
                   "pipelineExpression", "assignmentExpression", "assignmentOp", 
                   "conditionalExpression", "logicalOrExpression", "logicalAndExpression", 
                   "equalityExpression", "equalityOp", "relationalExpression", 
                   "relationalOp", "shiftExpression", "shiftOp", "additiveExpression", 
                   "addOp", "multiplicativeExpression", "mulOp", "unaryExpression", 
                   "postfixExpression", "postfix", "argumentList", "namedArgument", 
                   "primaryExpression", "literal", "vectorLiteral", "structLiteral", 
                   "structFields", "structField", "markupLiteral", "markupAttrs", 
                   "markupAttr", "markupContent", "interpolatedString", 
                   "expressionStatement", "type", "simpleType", "typeSuffix", 
                   "baseType", "optionalType", "unionType", "functionType", 
                   "genericType", "genericArgs", "genericParams", "decorator", 
                   "controlStatement", "loopStatement", "infiniteLoop", 
                   "rangeLoop", "conditionalStatement", "matchStatement", 
                   "matchCase" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    T__5=6
    T__6=7
    T__7=8
    T__8=9
    T__9=10
    T__10=11
    T__11=12
    T__12=13
    T__13=14
    T__14=15
    T__15=16
    T__16=17
    T__17=18
    T__18=19
    T__19=20
    T__20=21
    T__21=22
    T__22=23
    T__23=24
    T__24=25
    T__25=26
    LET=27
    CONST=28
    STATIC=29
    STRUCT=30
    TYPE=31
    DECLARE=32
    LOOP=33
    AWAIT=34
    ASYNC=35
    BREAK=36
    CONTINUE=37
    IMPORT=38
    EXPORT=39
    FROM=40
    MATCH=41
    CATCH=42
    THROW=43
    TYPEOF=44
    FN=45
    THIS=46
    TRUE=47
    FALSE=48
    VOID=49
    AS=50
    IN=51
    PLUS=52
    MINUS=53
    MUL=54
    DIV=55
    MOD=56
    AND=57
    OR=58
    XOR=59
    LSHIFT=60
    RSHIFT=61
    LAND=62
    LOR=63
    NOT=64
    EQ=65
    NE=66
    LT=67
    GT=68
    LE=69
    GE=70
    ASSIGN=71
    QMARK=72
    COLON=73
    SEMI=74
    COMMA=75
    DOT=76
    LPAREN=77
    RPAREN=78
    LBRACK=79
    RBRACK=80
    LBRACE=81
    RBRACE=82
    AT=83
    ARROW=84
    PIPE=85
    ELLIPSIS=86
    ID=87
    INT=88
    FLOAT=89
    STRING=90
    LINE_COMMENT=91
    BLOCK_COMMENT=92
    WS=93
    STRING_CONTENT=94

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

        def statement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.StatementContext)
            else:
                return self.getTypedRuleContext(EzLangParser.StatementContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_program

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterProgram" ):
                listener.enterProgram(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitProgram" ):
                listener.exitProgram(self)




    def program(self):

        localctx = EzLangParser.ProgramContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_program)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 149
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 13965506935527424) != 0) or ((((_la - 64)) & ~0x3f) == 0 and ((1 << (_la - 64)) & 126492681) != 0):
                self.state = 146
                self.statement()
                self.state = 151
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 152
            self.match(EzLangParser.EOF)
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

        def typeDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.TypeDeclarationContext,0)


        def variableDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.VariableDeclarationContext,0)


        def structDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.StructDeclarationContext,0)


        def functionDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.FunctionDeclarationContext,0)


        def importStatement(self):
            return self.getTypedRuleContext(EzLangParser.ImportStatementContext,0)


        def exportStatement(self):
            return self.getTypedRuleContext(EzLangParser.ExportStatementContext,0)


        def declareStatement(self):
            return self.getTypedRuleContext(EzLangParser.DeclareStatementContext,0)


        def expressionStatement(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionStatementContext,0)


        def blockStatement(self):
            return self.getTypedRuleContext(EzLangParser.BlockStatementContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_statement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStatement" ):
                listener.enterStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStatement" ):
                listener.exitStatement(self)




    def statement(self):

        localctx = EzLangParser.StatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_statement)
        try:
            self.state = 163
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,1,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 154
                self.typeDeclaration()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 155
                self.variableDeclaration()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 156
                self.structDeclaration()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 157
                self.functionDeclaration()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 158
                self.importStatement()
                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 159
                self.exportStatement()
                pass

            elif la_ == 7:
                self.enterOuterAlt(localctx, 7)
                self.state = 160
                self.declareStatement()
                pass

            elif la_ == 8:
                self.enterOuterAlt(localctx, 8)
                self.state = 161
                self.expressionStatement()
                pass

            elif la_ == 9:
                self.enterOuterAlt(localctx, 9)
                self.state = 162
                self.blockStatement()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def TYPE(self):
            return self.getToken(EzLangParser.TYPE, 0)

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def genericParams(self):
            return self.getTypedRuleContext(EzLangParser.GenericParamsContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_typeDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterTypeDeclaration" ):
                listener.enterTypeDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitTypeDeclaration" ):
                listener.exitTypeDeclaration(self)




    def typeDeclaration(self):

        localctx = EzLangParser.TypeDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_typeDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 165
            self.match(EzLangParser.TYPE)
            self.state = 166
            self.match(EzLangParser.ID)
            self.state = 168
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==67:
                self.state = 167
                self.genericParams()


            self.state = 170
            self.match(EzLangParser.ASSIGN)
            self.state = 171
            self.type_()
            self.state = 172
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class VariableDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def LET(self):
            return self.getToken(EzLangParser.LET, 0)

        def CONST(self):
            return self.getToken(EzLangParser.CONST, 0)

        def STATIC(self):
            return self.getToken(EzLangParser.STATIC, 0)

        def decorator(self):
            return self.getTypedRuleContext(EzLangParser.DecoratorContext,0)


        def genericParams(self):
            return self.getTypedRuleContext(EzLangParser.GenericParamsContext,0)


        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_variableDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterVariableDeclaration" ):
                listener.enterVariableDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitVariableDeclaration" ):
                listener.exitVariableDeclaration(self)




    def variableDeclaration(self):

        localctx = EzLangParser.VariableDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_variableDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 175
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==83:
                self.state = 174
                self.decorator()


            self.state = 177
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 939524096) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
            self.state = 178
            self.match(EzLangParser.ID)
            self.state = 180
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==67:
                self.state = 179
                self.genericParams()


            self.state = 184
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==73:
                self.state = 182
                self.match(EzLangParser.COLON)
                self.state = 183
                self.type_()


            self.state = 186
            self.match(EzLangParser.ASSIGN)
            self.state = 187
            self.expression()
            self.state = 188
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRUCT(self):
            return self.getToken(EzLangParser.STRUCT, 0)

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def structBody(self):
            return self.getTypedRuleContext(EzLangParser.StructBodyContext,0)


        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def genericParams(self):
            return self.getTypedRuleContext(EzLangParser.GenericParamsContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_structDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructDeclaration" ):
                listener.enterStructDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructDeclaration" ):
                listener.exitStructDeclaration(self)




    def structDeclaration(self):

        localctx = EzLangParser.StructDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_structDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 190
            self.match(EzLangParser.STRUCT)
            self.state = 191
            self.match(EzLangParser.ID)
            self.state = 193
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==67:
                self.state = 192
                self.genericParams()


            self.state = 195
            self.match(EzLangParser.LBRACE)
            self.state = 196
            self.structBody()
            self.state = 197
            self.match(EzLangParser.RBRACE)
            self.state = 198
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructBodyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def baseStruct(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.BaseStructContext)
            else:
                return self.getTypedRuleContext(EzLangParser.BaseStructContext,i)


        def field(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.FieldContext)
            else:
                return self.getTypedRuleContext(EzLangParser.FieldContext,i)


        def method(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MethodContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MethodContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_structBody

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructBody" ):
                listener.enterStructBody(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructBody" ):
                listener.exitStructBody(self)




    def structBody(self):

        localctx = EzLangParser.StructBodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_structBody)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 205
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==86 or _la==87:
                self.state = 203
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,7,self._ctx)
                if la_ == 1:
                    self.state = 200
                    self.baseStruct()
                    pass

                elif la_ == 2:
                    self.state = 201
                    self.field()
                    pass

                elif la_ == 3:
                    self.state = 202
                    self.method()
                    pass


                self.state = 207
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BaseStructContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ELLIPSIS(self):
            return self.getToken(EzLangParser.ELLIPSIS, 0)

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_baseStruct

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBaseStruct" ):
                listener.enterBaseStruct(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBaseStruct" ):
                listener.exitBaseStruct(self)




    def baseStruct(self):

        localctx = EzLangParser.BaseStructContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_baseStruct)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 208
            self.match(EzLangParser.ELLIPSIS)
            self.state = 209
            self.match(EzLangParser.ID)
            self.state = 210
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FieldContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_field

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterField" ):
                listener.enterField(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitField" ):
                listener.exitField(self)




    def field(self):

        localctx = EzLangParser.FieldContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_field)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 212
            self.match(EzLangParser.ID)
            self.state = 213
            self.match(EzLangParser.COLON)
            self.state = 214
            self.type_()
            self.state = 217
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==71:
                self.state = 215
                self.match(EzLangParser.ASSIGN)
                self.state = 216
                self.expression()


            self.state = 219
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MethodContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def functionExpression(self):
            return self.getTypedRuleContext(EzLangParser.FunctionExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_method

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMethod" ):
                listener.enterMethod(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMethod" ):
                listener.exitMethod(self)




    def method(self):

        localctx = EzLangParser.MethodContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_method)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 221
            self.match(EzLangParser.ID)
            self.state = 222
            self.match(EzLangParser.ASSIGN)
            self.state = 223
            self.functionExpression()
            self.state = 224
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CONST(self):
            return self.getToken(EzLangParser.CONST, 0)

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def functionExpression(self):
            return self.getTypedRuleContext(EzLangParser.FunctionExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def ASYNC(self):
            return self.getToken(EzLangParser.ASYNC, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_functionDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunctionDeclaration" ):
                listener.enterFunctionDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunctionDeclaration" ):
                listener.exitFunctionDeclaration(self)




    def functionDeclaration(self):

        localctx = EzLangParser.FunctionDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_functionDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 227
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==35:
                self.state = 226
                self.match(EzLangParser.ASYNC)


            self.state = 229
            self.match(EzLangParser.CONST)
            self.state = 230
            self.match(EzLangParser.ID)
            self.state = 231
            self.match(EzLangParser.ASSIGN)
            self.state = 232
            self.functionExpression()
            self.state = 233
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def blockOrExpression(self):
            return self.getTypedRuleContext(EzLangParser.BlockOrExpressionContext,0)


        def parameters(self):
            return self.getTypedRuleContext(EzLangParser.ParametersContext,0)


        def ARROW(self):
            return self.getToken(EzLangParser.ARROW, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_functionExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunctionExpression" ):
                listener.enterFunctionExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunctionExpression" ):
                listener.exitFunctionExpression(self)




    def functionExpression(self):

        localctx = EzLangParser.FunctionExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_functionExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 235
            self.match(EzLangParser.LPAREN)
            self.state = 237
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==87:
                self.state = 236
                self.parameters()


            self.state = 239
            self.match(EzLangParser.RPAREN)
            self.state = 242
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,12,self._ctx)
            if la_ == 1:
                self.state = 240
                self.match(EzLangParser.ARROW)
                self.state = 241
                self.type_()


            self.state = 244
            self.blockOrExpression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParametersContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def parameter(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ParameterContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ParameterContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_parameters

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterParameters" ):
                listener.enterParameters(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitParameters" ):
                listener.exitParameters(self)




    def parameters(self):

        localctx = EzLangParser.ParametersContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_parameters)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 246
            self.parameter()
            self.state = 251
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==75:
                self.state = 247
                self.match(EzLangParser.COMMA)
                self.state = 248
                self.parameter()
                self.state = 253
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParameterContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def QMARK(self):
            return self.getToken(EzLangParser.QMARK, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_parameter

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterParameter" ):
                listener.enterParameter(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitParameter" ):
                listener.exitParameter(self)




    def parameter(self):

        localctx = EzLangParser.ParameterContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_parameter)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 254
            self.match(EzLangParser.ID)
            self.state = 256
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==72:
                self.state = 255
                self.match(EzLangParser.QMARK)


            self.state = 258
            self.match(EzLangParser.COLON)
            self.state = 259
            self.type_()
            self.state = 262
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==71:
                self.state = 260
                self.match(EzLangParser.ASSIGN)
                self.state = 261
                self.expression()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BlockOrExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def ARROW(self):
            return self.getToken(EzLangParser.ARROW, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_blockOrExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBlockOrExpression" ):
                listener.enterBlockOrExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBlockOrExpression" ):
                listener.exitBlockOrExpression(self)




    def blockOrExpression(self):

        localctx = EzLangParser.BlockOrExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_blockOrExpression)
        try:
            self.state = 267
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [81]:
                self.enterOuterAlt(localctx, 1)
                self.state = 264
                self.block()
                pass
            elif token in [84]:
                self.enterOuterAlt(localctx, 2)
                self.state = 265
                self.match(EzLangParser.ARROW)
                self.state = 266
                self.expression()
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

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBlock" ):
                listener.enterBlock(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBlock" ):
                listener.exitBlock(self)




    def block(self):

        localctx = EzLangParser.BlockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_block)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 269
            self.match(EzLangParser.LBRACE)
            self.state = 273
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 13965506935527424) != 0) or ((((_la - 64)) & ~0x3f) == 0 and ((1 << (_la - 64)) & 126492681) != 0):
                self.state = 270
                self.statement()
                self.state = 275
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 276
            self.match(EzLangParser.RBRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BlockStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_blockStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBlockStatement" ):
                listener.enterBlockStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBlockStatement" ):
                listener.exitBlockStatement(self)




    def blockStatement(self):

        localctx = EzLangParser.BlockStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_blockStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 278
            self.block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ImportStatementContext(ParserRuleContext):
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

        def importItems(self):
            return self.getTypedRuleContext(EzLangParser.ImportItemsContext,0)


        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_importStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterImportStatement" ):
                listener.enterImportStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitImportStatement" ):
                listener.exitImportStatement(self)




    def importStatement(self):

        localctx = EzLangParser.ImportStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_importStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 280
            self.match(EzLangParser.FROM)
            self.state = 281
            self.match(EzLangParser.STRING)
            self.state = 282
            self.match(EzLangParser.IMPORT)
            self.state = 283
            self.match(EzLangParser.LBRACE)
            self.state = 284
            self.importItems()
            self.state = 285
            self.match(EzLangParser.RBRACE)
            self.state = 286
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ImportItemsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def importItem(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ImportItemContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ImportItemContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_importItems

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterImportItems" ):
                listener.enterImportItems(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitImportItems" ):
                listener.exitImportItems(self)




    def importItems(self):

        localctx = EzLangParser.ImportItemsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_importItems)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 288
            self.importItem()
            self.state = 293
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==75:
                self.state = 289
                self.match(EzLangParser.COMMA)
                self.state = 290
                self.importItem()
                self.state = 295
                self._errHandler.sync(self)
                _la = self._input.LA(1)

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

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.ID)
            else:
                return self.getToken(EzLangParser.ID, i)

        def AS(self):
            return self.getToken(EzLangParser.AS, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_importItem

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterImportItem" ):
                listener.enterImportItem(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitImportItem" ):
                listener.exitImportItem(self)




    def importItem(self):

        localctx = EzLangParser.ImportItemContext(self, self._ctx, self.state)
        self.enterRule(localctx, 36, self.RULE_importItem)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 296
            self.match(EzLangParser.ID)
            self.state = 299
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==50:
                self.state = 297
                self.match(EzLangParser.AS)
                self.state = 298
                self.match(EzLangParser.ID)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExportStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EXPORT(self):
            return self.getToken(EzLangParser.EXPORT, 0)

        def variableDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.VariableDeclarationContext,0)


        def structDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.StructDeclarationContext,0)


        def functionDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.FunctionDeclarationContext,0)


        def typeDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.TypeDeclarationContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_exportStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExportStatement" ):
                listener.enterExportStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExportStatement" ):
                listener.exitExportStatement(self)




    def exportStatement(self):

        localctx = EzLangParser.ExportStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 38, self.RULE_exportStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 301
            self.match(EzLangParser.EXPORT)
            self.state = 306
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,20,self._ctx)
            if la_ == 1:
                self.state = 302
                self.variableDeclaration()
                pass

            elif la_ == 2:
                self.state = 303
                self.structDeclaration()
                pass

            elif la_ == 3:
                self.state = 304
                self.functionDeclaration()
                pass

            elif la_ == 4:
                self.state = 305
                self.typeDeclaration()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DeclareStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DECLARE(self):
            return self.getToken(EzLangParser.DECLARE, 0)

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def CONST(self):
            return self.getToken(EzLangParser.CONST, 0)

        def LET(self):
            return self.getToken(EzLangParser.LET, 0)

        def STATIC(self):
            return self.getToken(EzLangParser.STATIC, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_declareStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDeclareStatement" ):
                listener.enterDeclareStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDeclareStatement" ):
                listener.exitDeclareStatement(self)




    def declareStatement(self):

        localctx = EzLangParser.DeclareStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 40, self.RULE_declareStatement)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 308
            self.match(EzLangParser.DECLARE)
            self.state = 310
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 939524096) != 0):
                self.state = 309
                _la = self._input.LA(1)
                if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 939524096) != 0)):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()


            self.state = 312
            self.match(EzLangParser.ID)
            self.state = 313
            self.match(EzLangParser.COLON)
            self.state = 314
            self.type_()
            self.state = 315
            self.match(EzLangParser.SEMI)
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

        def pipelineExpression(self):
            return self.getTypedRuleContext(EzLangParser.PipelineExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_expression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpression" ):
                listener.enterExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpression" ):
                listener.exitExpression(self)




    def expression(self):

        localctx = EzLangParser.ExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 42, self.RULE_expression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 317
            self.pipelineExpression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PipelineExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def conditionalExpression(self):
            return self.getTypedRuleContext(EzLangParser.ConditionalExpressionContext,0)


        def PIPE(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.PIPE)
            else:
                return self.getToken(EzLangParser.PIPE, i)

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.ID)
            else:
                return self.getToken(EzLangParser.ID, i)

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

        def argumentList(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ArgumentListContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ArgumentListContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_pipelineExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPipelineExpression" ):
                listener.enterPipelineExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPipelineExpression" ):
                listener.exitPipelineExpression(self)




    def pipelineExpression(self):

        localctx = EzLangParser.PipelineExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 44, self.RULE_pipelineExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 319
            self.conditionalExpression()
            self.state = 329
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,23,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 320
                    self.match(EzLangParser.PIPE)
                    self.state = 321
                    self.match(EzLangParser.ID)
                    self.state = 322
                    self.match(EzLangParser.LPAREN)
                    self.state = 324
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if (((_la) & ~0x3f) == 0 and ((1 << _la) & 13963814852630528) != 0) or ((((_la - 64)) & ~0x3f) == 0 and ((1 << (_la - 64)) & 125837321) != 0):
                        self.state = 323
                        self.argumentList()


                    self.state = 326
                    self.match(EzLangParser.RPAREN) 
                self.state = 331
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,23,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssignmentExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def conditionalExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ConditionalExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ConditionalExpressionContext,i)


        def assignmentOp(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.AssignmentOpContext)
            else:
                return self.getTypedRuleContext(EzLangParser.AssignmentOpContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_assignmentExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAssignmentExpression" ):
                listener.enterAssignmentExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAssignmentExpression" ):
                listener.exitAssignmentExpression(self)




    def assignmentExpression(self):

        localctx = EzLangParser.AssignmentExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 46, self.RULE_assignmentExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 332
            self.conditionalExpression()
            self.state = 338
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 2046) != 0) or _la==71:
                self.state = 333
                self.assignmentOp()
                self.state = 334
                self.conditionalExpression()
                self.state = 340
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssignmentOpContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_assignmentOp

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAssignmentOp" ):
                listener.enterAssignmentOp(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAssignmentOp" ):
                listener.exitAssignmentOp(self)




    def assignmentOp(self):

        localctx = EzLangParser.AssignmentOpContext(self, self._ctx, self.state)
        self.enterRule(localctx, 48, self.RULE_assignmentOp)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 341
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 2046) != 0) or _la==71):
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


    class ConditionalExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def logicalOrExpression(self):
            return self.getTypedRuleContext(EzLangParser.LogicalOrExpressionContext,0)


        def QMARK(self):
            return self.getToken(EzLangParser.QMARK, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_conditionalExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterConditionalExpression" ):
                listener.enterConditionalExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitConditionalExpression" ):
                listener.exitConditionalExpression(self)




    def conditionalExpression(self):

        localctx = EzLangParser.ConditionalExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 50, self.RULE_conditionalExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 343
            self.logicalOrExpression()
            self.state = 349
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,25,self._ctx)
            if la_ == 1:
                self.state = 344
                self.match(EzLangParser.QMARK)
                self.state = 345
                self.expression()
                self.state = 346
                self.match(EzLangParser.COLON)
                self.state = 347
                self.expression()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LogicalOrExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def logicalAndExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.LogicalAndExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.LogicalAndExpressionContext,i)


        def LOR(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.LOR)
            else:
                return self.getToken(EzLangParser.LOR, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_logicalOrExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLogicalOrExpression" ):
                listener.enterLogicalOrExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLogicalOrExpression" ):
                listener.exitLogicalOrExpression(self)




    def logicalOrExpression(self):

        localctx = EzLangParser.LogicalOrExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 52, self.RULE_logicalOrExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 351
            self.logicalAndExpression()
            self.state = 356
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,26,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 352
                    self.match(EzLangParser.LOR)
                    self.state = 353
                    self.logicalAndExpression() 
                self.state = 358
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,26,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LogicalAndExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def equalityExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.EqualityExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.EqualityExpressionContext,i)


        def LAND(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.LAND)
            else:
                return self.getToken(EzLangParser.LAND, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_logicalAndExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLogicalAndExpression" ):
                listener.enterLogicalAndExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLogicalAndExpression" ):
                listener.exitLogicalAndExpression(self)




    def logicalAndExpression(self):

        localctx = EzLangParser.LogicalAndExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 54, self.RULE_logicalAndExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 359
            self.equalityExpression()
            self.state = 364
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,27,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 360
                    self.match(EzLangParser.LAND)
                    self.state = 361
                    self.equalityExpression() 
                self.state = 366
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,27,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EqualityExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def relationalExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.RelationalExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.RelationalExpressionContext,i)


        def equalityOp(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.EqualityOpContext)
            else:
                return self.getTypedRuleContext(EzLangParser.EqualityOpContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_equalityExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEqualityExpression" ):
                listener.enterEqualityExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEqualityExpression" ):
                listener.exitEqualityExpression(self)




    def equalityExpression(self):

        localctx = EzLangParser.EqualityExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 56, self.RULE_equalityExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 367
            self.relationalExpression()
            self.state = 373
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,28,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 368
                    self.equalityOp()
                    self.state = 369
                    self.relationalExpression() 
                self.state = 375
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,28,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EqualityOpContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EQ(self):
            return self.getToken(EzLangParser.EQ, 0)

        def NE(self):
            return self.getToken(EzLangParser.NE, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_equalityOp

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEqualityOp" ):
                listener.enterEqualityOp(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEqualityOp" ):
                listener.exitEqualityOp(self)




    def equalityOp(self):

        localctx = EzLangParser.EqualityOpContext(self, self._ctx, self.state)
        self.enterRule(localctx, 58, self.RULE_equalityOp)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 376
            _la = self._input.LA(1)
            if not(_la==65 or _la==66):
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


    class RelationalExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def shiftExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ShiftExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ShiftExpressionContext,i)


        def relationalOp(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.RelationalOpContext)
            else:
                return self.getTypedRuleContext(EzLangParser.RelationalOpContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_relationalExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRelationalExpression" ):
                listener.enterRelationalExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRelationalExpression" ):
                listener.exitRelationalExpression(self)




    def relationalExpression(self):

        localctx = EzLangParser.RelationalExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 60, self.RULE_relationalExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 378
            self.shiftExpression()
            self.state = 384
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,29,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 379
                    self.relationalOp()
                    self.state = 380
                    self.shiftExpression() 
                self.state = 386
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,29,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RelationalOpContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def LE(self):
            return self.getToken(EzLangParser.LE, 0)

        def GE(self):
            return self.getToken(EzLangParser.GE, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_relationalOp

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRelationalOp" ):
                listener.enterRelationalOp(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRelationalOp" ):
                listener.exitRelationalOp(self)




    def relationalOp(self):

        localctx = EzLangParser.RelationalOpContext(self, self._ctx, self.state)
        self.enterRule(localctx, 62, self.RULE_relationalOp)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 387
            _la = self._input.LA(1)
            if not(((((_la - 67)) & ~0x3f) == 0 and ((1 << (_la - 67)) & 15) != 0)):
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


    class ShiftExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def additiveExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.AdditiveExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.AdditiveExpressionContext,i)


        def shiftOp(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ShiftOpContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ShiftOpContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_shiftExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterShiftExpression" ):
                listener.enterShiftExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitShiftExpression" ):
                listener.exitShiftExpression(self)




    def shiftExpression(self):

        localctx = EzLangParser.ShiftExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 64, self.RULE_shiftExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 389
            self.additiveExpression()
            self.state = 395
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,30,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 390
                    self.shiftOp()
                    self.state = 391
                    self.additiveExpression() 
                self.state = 397
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,30,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ShiftOpContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LSHIFT(self):
            return self.getToken(EzLangParser.LSHIFT, 0)

        def RSHIFT(self):
            return self.getToken(EzLangParser.RSHIFT, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_shiftOp

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterShiftOp" ):
                listener.enterShiftOp(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitShiftOp" ):
                listener.exitShiftOp(self)




    def shiftOp(self):

        localctx = EzLangParser.ShiftOpContext(self, self._ctx, self.state)
        self.enterRule(localctx, 66, self.RULE_shiftOp)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 398
            _la = self._input.LA(1)
            if not(_la==60 or _la==61):
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


    class AdditiveExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def multiplicativeExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MultiplicativeExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MultiplicativeExpressionContext,i)


        def addOp(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.AddOpContext)
            else:
                return self.getTypedRuleContext(EzLangParser.AddOpContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_additiveExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAdditiveExpression" ):
                listener.enterAdditiveExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAdditiveExpression" ):
                listener.exitAdditiveExpression(self)




    def additiveExpression(self):

        localctx = EzLangParser.AdditiveExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 68, self.RULE_additiveExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 400
            self.multiplicativeExpression()
            self.state = 406
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,31,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 401
                    self.addOp()
                    self.state = 402
                    self.multiplicativeExpression() 
                self.state = 408
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,31,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AddOpContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def PLUS(self):
            return self.getToken(EzLangParser.PLUS, 0)

        def MINUS(self):
            return self.getToken(EzLangParser.MINUS, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_addOp

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAddOp" ):
                listener.enterAddOp(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAddOp" ):
                listener.exitAddOp(self)




    def addOp(self):

        localctx = EzLangParser.AddOpContext(self, self._ctx, self.state)
        self.enterRule(localctx, 70, self.RULE_addOp)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 409
            _la = self._input.LA(1)
            if not(_la==52 or _la==53):
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


    class MultiplicativeExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def unaryExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.UnaryExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.UnaryExpressionContext,i)


        def mulOp(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MulOpContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MulOpContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_multiplicativeExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMultiplicativeExpression" ):
                listener.enterMultiplicativeExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMultiplicativeExpression" ):
                listener.exitMultiplicativeExpression(self)




    def multiplicativeExpression(self):

        localctx = EzLangParser.MultiplicativeExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 72, self.RULE_multiplicativeExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 411
            self.unaryExpression()
            self.state = 417
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,32,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 412
                    self.mulOp()
                    self.state = 413
                    self.unaryExpression() 
                self.state = 419
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,32,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MulOpContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def MUL(self):
            return self.getToken(EzLangParser.MUL, 0)

        def DIV(self):
            return self.getToken(EzLangParser.DIV, 0)

        def MOD(self):
            return self.getToken(EzLangParser.MOD, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_mulOp

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMulOp" ):
                listener.enterMulOp(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMulOp" ):
                listener.exitMulOp(self)




    def mulOp(self):

        localctx = EzLangParser.MulOpContext(self, self._ctx, self.state)
        self.enterRule(localctx, 74, self.RULE_mulOp)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 420
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 126100789566373888) != 0)):
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


    class UnaryExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def unaryExpression(self):
            return self.getTypedRuleContext(EzLangParser.UnaryExpressionContext,0)


        def PLUS(self):
            return self.getToken(EzLangParser.PLUS, 0)

        def MINUS(self):
            return self.getToken(EzLangParser.MINUS, 0)

        def NOT(self):
            return self.getToken(EzLangParser.NOT, 0)

        def postfixExpression(self):
            return self.getTypedRuleContext(EzLangParser.PostfixExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_unaryExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterUnaryExpression" ):
                listener.enterUnaryExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitUnaryExpression" ):
                listener.exitUnaryExpression(self)




    def unaryExpression(self):

        localctx = EzLangParser.UnaryExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 76, self.RULE_unaryExpression)
        self._la = 0 # Token type
        try:
            self.state = 425
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [11, 52, 53, 64]:
                self.enterOuterAlt(localctx, 1)
                self.state = 422
                _la = self._input.LA(1)
                if not(((((_la - 11)) & ~0x3f) == 0 and ((1 << (_la - 11)) & 9013796324507649) != 0)):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 423
                self.unaryExpression()
                pass
            elif token in [12, 34, 42, 43, 44, 47, 48, 67, 77, 87, 88, 89, 90]:
                self.enterOuterAlt(localctx, 2)
                self.state = 424
                self.postfixExpression()
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


    class PostfixExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def primaryExpression(self):
            return self.getTypedRuleContext(EzLangParser.PrimaryExpressionContext,0)


        def postfix(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.PostfixContext)
            else:
                return self.getTypedRuleContext(EzLangParser.PostfixContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_postfixExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPostfixExpression" ):
                listener.enterPostfixExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPostfixExpression" ):
                listener.exitPostfixExpression(self)




    def postfixExpression(self):

        localctx = EzLangParser.PostfixExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 78, self.RULE_postfixExpression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 427
            self.primaryExpression()
            self.state = 431
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,34,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 428
                    self.postfix() 
                self.state = 433
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,34,self._ctx)

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

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def argumentList(self):
            return self.getTypedRuleContext(EzLangParser.ArgumentListContext,0)


        def LBRACK(self):
            return self.getToken(EzLangParser.LBRACK, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def RBRACK(self):
            return self.getToken(EzLangParser.RBRACK, 0)

        def NOT(self):
            return self.getToken(EzLangParser.NOT, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_postfix

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPostfix" ):
                listener.enterPostfix(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPostfix" ):
                listener.exitPostfix(self)




    def postfix(self):

        localctx = EzLangParser.PostfixContext(self, self._ctx, self.state)
        self.enterRule(localctx, 80, self.RULE_postfix)
        self._la = 0 # Token type
        try:
            self.state = 446
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [76]:
                self.enterOuterAlt(localctx, 1)
                self.state = 434
                self.match(EzLangParser.DOT)
                self.state = 435
                self.match(EzLangParser.ID)
                pass
            elif token in [77]:
                self.enterOuterAlt(localctx, 2)
                self.state = 436
                self.match(EzLangParser.LPAREN)
                self.state = 438
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if (((_la) & ~0x3f) == 0 and ((1 << _la) & 13963814852630528) != 0) or ((((_la - 64)) & ~0x3f) == 0 and ((1 << (_la - 64)) & 125837321) != 0):
                    self.state = 437
                    self.argumentList()


                self.state = 440
                self.match(EzLangParser.RPAREN)
                pass
            elif token in [79]:
                self.enterOuterAlt(localctx, 3)
                self.state = 441
                self.match(EzLangParser.LBRACK)
                self.state = 442
                self.expression()
                self.state = 443
                self.match(EzLangParser.RBRACK)
                pass
            elif token in [64]:
                self.enterOuterAlt(localctx, 4)
                self.state = 445
                self.match(EzLangParser.NOT)
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


    class ArgumentListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def namedArgument(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.NamedArgumentContext)
            else:
                return self.getTypedRuleContext(EzLangParser.NamedArgumentContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_argumentList

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArgumentList" ):
                listener.enterArgumentList(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArgumentList" ):
                listener.exitArgumentList(self)




    def argumentList(self):

        localctx = EzLangParser.ArgumentListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 82, self.RULE_argumentList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 448
            self.namedArgument()
            self.state = 453
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==75:
                self.state = 449
                self.match(EzLangParser.COMMA)
                self.state = 450
                self.namedArgument()
                self.state = 455
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NamedArgumentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_namedArgument

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterNamedArgument" ):
                listener.enterNamedArgument(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitNamedArgument" ):
                listener.exitNamedArgument(self)




    def namedArgument(self):

        localctx = EzLangParser.NamedArgumentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 84, self.RULE_namedArgument)
        try:
            self.state = 460
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,38,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 456
                self.match(EzLangParser.ID)
                self.state = 457
                self.match(EzLangParser.ASSIGN)
                self.state = 458
                self.expression()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 459
                self.expression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PrimaryExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def literal(self):
            return self.getTypedRuleContext(EzLangParser.LiteralContext,0)


        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def vectorLiteral(self):
            return self.getTypedRuleContext(EzLangParser.VectorLiteralContext,0)


        def structLiteral(self):
            return self.getTypedRuleContext(EzLangParser.StructLiteralContext,0)


        def markupLiteral(self):
            return self.getTypedRuleContext(EzLangParser.MarkupLiteralContext,0)


        def TYPEOF(self):
            return self.getToken(EzLangParser.TYPEOF, 0)

        def CATCH(self):
            return self.getToken(EzLangParser.CATCH, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def THROW(self):
            return self.getToken(EzLangParser.THROW, 0)

        def AWAIT(self):
            return self.getToken(EzLangParser.AWAIT, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_primaryExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPrimaryExpression" ):
                listener.enterPrimaryExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPrimaryExpression" ):
                listener.exitPrimaryExpression(self)




    def primaryExpression(self):

        localctx = EzLangParser.PrimaryExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 86, self.RULE_primaryExpression)
        try:
            self.state = 482
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,39,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 462
                self.literal()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 463
                self.match(EzLangParser.ID)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 464
                self.match(EzLangParser.LPAREN)
                self.state = 465
                self.expression()
                self.state = 466
                self.match(EzLangParser.RPAREN)
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 468
                self.vectorLiteral()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 469
                self.structLiteral()
                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 470
                self.markupLiteral()
                pass

            elif la_ == 7:
                self.enterOuterAlt(localctx, 7)
                self.state = 471
                self.match(EzLangParser.TYPEOF)
                self.state = 472
                self.match(EzLangParser.LPAREN)
                self.state = 473
                self.expression()
                self.state = 474
                self.match(EzLangParser.RPAREN)
                pass

            elif la_ == 8:
                self.enterOuterAlt(localctx, 8)
                self.state = 476
                self.match(EzLangParser.CATCH)
                self.state = 477
                self.block()
                pass

            elif la_ == 9:
                self.enterOuterAlt(localctx, 9)
                self.state = 478
                self.match(EzLangParser.THROW)
                self.state = 479
                self.expression()
                pass

            elif la_ == 10:
                self.enterOuterAlt(localctx, 10)
                self.state = 480
                self.match(EzLangParser.AWAIT)
                self.state = 481
                self.expression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def INT(self):
            return self.getToken(EzLangParser.INT, 0)

        def FLOAT(self):
            return self.getToken(EzLangParser.FLOAT, 0)

        def STRING(self):
            return self.getToken(EzLangParser.STRING, 0)

        def TRUE(self):
            return self.getToken(EzLangParser.TRUE, 0)

        def FALSE(self):
            return self.getToken(EzLangParser.FALSE, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_literal

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLiteral" ):
                listener.enterLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLiteral" ):
                listener.exitLiteral(self)




    def literal(self):

        localctx = EzLangParser.LiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 88, self.RULE_literal)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 484
            _la = self._input.LA(1)
            if not(((((_la - 47)) & ~0x3f) == 0 and ((1 << (_la - 47)) & 15393162788867) != 0)):
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


    class VectorLiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACK(self):
            return self.getToken(EzLangParser.LBRACK, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def RBRACK(self):
            return self.getToken(EzLangParser.RBRACK, 0)

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def simpleType(self):
            return self.getTypedRuleContext(EzLangParser.SimpleTypeContext,0)


        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_vectorLiteral

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterVectorLiteral" ):
                listener.enterVectorLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitVectorLiteral" ):
                listener.exitVectorLiteral(self)




    def vectorLiteral(self):

        localctx = EzLangParser.VectorLiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 90, self.RULE_vectorLiteral)
        self._la = 0 # Token type
        try:
            self.state = 516
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,43,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 486
                self.match(EzLangParser.T__11)
                self.state = 491
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==67:
                    self.state = 487
                    self.match(EzLangParser.LT)
                    self.state = 488
                    self.simpleType()
                    self.state = 489
                    self.match(EzLangParser.GT)


                self.state = 493
                self.match(EzLangParser.LBRACK)
                self.state = 494
                self.expression()
                self.state = 499
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==75:
                    self.state = 495
                    self.match(EzLangParser.COMMA)
                    self.state = 496
                    self.expression()
                    self.state = 501
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                self.state = 502
                self.match(EzLangParser.RBRACK)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 504
                self.match(EzLangParser.T__11)
                self.state = 505
                self.match(EzLangParser.LBRACK)
                self.state = 506
                self.expression()
                self.state = 511
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==75:
                    self.state = 507
                    self.match(EzLangParser.COMMA)
                    self.state = 508
                    self.expression()
                    self.state = 513
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                self.state = 514
                self.match(EzLangParser.RBRACK)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructLiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def genericArgs(self):
            return self.getTypedRuleContext(EzLangParser.GenericArgsContext,0)


        def structFields(self):
            return self.getTypedRuleContext(EzLangParser.StructFieldsContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_structLiteral

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructLiteral" ):
                listener.enterStructLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructLiteral" ):
                listener.exitStructLiteral(self)




    def structLiteral(self):

        localctx = EzLangParser.StructLiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 92, self.RULE_structLiteral)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 518
            self.match(EzLangParser.ID)
            self.state = 520
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==67:
                self.state = 519
                self.genericArgs()


            self.state = 522
            self.match(EzLangParser.LPAREN)
            self.state = 524
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==86 or _la==87:
                self.state = 523
                self.structFields()


            self.state = 526
            self.match(EzLangParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructFieldsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def structField(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.StructFieldContext)
            else:
                return self.getTypedRuleContext(EzLangParser.StructFieldContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_structFields

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructFields" ):
                listener.enterStructFields(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructFields" ):
                listener.exitStructFields(self)




    def structFields(self):

        localctx = EzLangParser.StructFieldsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 94, self.RULE_structFields)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 528
            self.structField()
            self.state = 533
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==75:
                self.state = 529
                self.match(EzLangParser.COMMA)
                self.state = 530
                self.structField()
                self.state = 535
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructFieldContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def ELLIPSIS(self):
            return self.getToken(EzLangParser.ELLIPSIS, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_structField

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructField" ):
                listener.enterStructField(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructField" ):
                listener.exitStructField(self)




    def structField(self):

        localctx = EzLangParser.StructFieldContext(self, self._ctx, self.state)
        self.enterRule(localctx, 96, self.RULE_structField)
        try:
            self.state = 541
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [87]:
                self.enterOuterAlt(localctx, 1)
                self.state = 536
                self.match(EzLangParser.ID)
                self.state = 537
                self.match(EzLangParser.ASSIGN)
                self.state = 538
                self.expression()
                pass
            elif token in [86]:
                self.enterOuterAlt(localctx, 2)
                self.state = 539
                self.match(EzLangParser.ELLIPSIS)
                self.state = 540
                self.expression()
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


    class MarkupLiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.LT)
            else:
                return self.getToken(EzLangParser.LT, i)

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.ID)
            else:
                return self.getToken(EzLangParser.ID, i)

        def GT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.GT)
            else:
                return self.getToken(EzLangParser.GT, i)

        def DIV(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.DIV)
            else:
                return self.getToken(EzLangParser.DIV, i)

        def markupContent(self):
            return self.getTypedRuleContext(EzLangParser.MarkupContentContext,0)


        def markupAttrs(self):
            return self.getTypedRuleContext(EzLangParser.MarkupAttrsContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_markupLiteral

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMarkupLiteral" ):
                listener.enterMarkupLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMarkupLiteral" ):
                listener.exitMarkupLiteral(self)




    def markupLiteral(self):

        localctx = EzLangParser.MarkupLiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 98, self.RULE_markupLiteral)
        self._la = 0 # Token type
        try:
            self.state = 564
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,51,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 543
                self.match(EzLangParser.LT)
                self.state = 544
                self.match(EzLangParser.ID)
                self.state = 546
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==87:
                    self.state = 545
                    self.markupAttrs()


                self.state = 548
                self.match(EzLangParser.GT)
                self.state = 551
                self._errHandler.sync(self)
                token = self._input.LA(1)
                if token in [67, 81, 90]:
                    self.state = 549
                    self.markupContent()
                    pass
                elif token in [55]:
                    self.state = 550
                    self.match(EzLangParser.DIV)
                    pass
                else:
                    raise NoViableAltException(self)

                self.state = 553
                self.match(EzLangParser.LT)
                self.state = 554
                self.match(EzLangParser.DIV)
                self.state = 555
                self.match(EzLangParser.ID)
                self.state = 556
                self.match(EzLangParser.GT)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 557
                self.match(EzLangParser.LT)
                self.state = 558
                self.match(EzLangParser.ID)
                self.state = 560
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==87:
                    self.state = 559
                    self.markupAttrs()


                self.state = 562
                self.match(EzLangParser.DIV)
                self.state = 563
                self.match(EzLangParser.GT)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MarkupAttrsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def markupAttr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MarkupAttrContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MarkupAttrContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_markupAttrs

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMarkupAttrs" ):
                listener.enterMarkupAttrs(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMarkupAttrs" ):
                listener.exitMarkupAttrs(self)




    def markupAttrs(self):

        localctx = EzLangParser.MarkupAttrsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 100, self.RULE_markupAttrs)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 567 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 566
                self.markupAttr()
                self.state = 569 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==87):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MarkupAttrContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def ASSIGN(self):
            return self.getToken(EzLangParser.ASSIGN, 0)

        def STRING(self):
            return self.getToken(EzLangParser.STRING, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_markupAttr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMarkupAttr" ):
                listener.enterMarkupAttr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMarkupAttr" ):
                listener.exitMarkupAttr(self)




    def markupAttr(self):

        localctx = EzLangParser.MarkupAttrContext(self, self._ctx, self.state)
        self.enterRule(localctx, 102, self.RULE_markupAttr)
        try:
            self.state = 577
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,53,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 571
                self.match(EzLangParser.ID)
                self.state = 572
                self.match(EzLangParser.ASSIGN)
                self.state = 573
                self.match(EzLangParser.STRING)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 574
                self.match(EzLangParser.ID)
                self.state = 575
                self.match(EzLangParser.ASSIGN)
                self.state = 576
                self.expression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MarkupContentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.STRING)
            else:
                return self.getToken(EzLangParser.STRING, i)

        def LBRACE(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.LBRACE)
            else:
                return self.getToken(EzLangParser.LBRACE, i)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def RBRACE(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.RBRACE)
            else:
                return self.getToken(EzLangParser.RBRACE, i)

        def markupLiteral(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MarkupLiteralContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MarkupLiteralContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_markupContent

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMarkupContent" ):
                listener.enterMarkupContent(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMarkupContent" ):
                listener.exitMarkupContent(self)




    def markupContent(self):

        localctx = EzLangParser.MarkupContentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 104, self.RULE_markupContent)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 587
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,55,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 585
                    self._errHandler.sync(self)
                    token = self._input.LA(1)
                    if token in [90]:
                        self.state = 579
                        self.match(EzLangParser.STRING)
                        pass
                    elif token in [81]:
                        self.state = 580
                        self.match(EzLangParser.LBRACE)
                        self.state = 581
                        self.expression()
                        self.state = 582
                        self.match(EzLangParser.RBRACE)
                        pass
                    elif token in [67]:
                        self.state = 584
                        self.markupLiteral()
                        pass
                    else:
                        raise NoViableAltException(self)
             
                self.state = 589
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,55,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class InterpolatedStringContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING_CONTENT(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.STRING_CONTENT)
            else:
                return self.getToken(EzLangParser.STRING_CONTENT, i)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_interpolatedString

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInterpolatedString" ):
                listener.enterInterpolatedString(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInterpolatedString" ):
                listener.exitInterpolatedString(self)




    def interpolatedString(self):

        localctx = EzLangParser.InterpolatedStringContext(self, self._ctx, self.state)
        self.enterRule(localctx, 106, self.RULE_interpolatedString)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 590
            self.match(EzLangParser.T__12)
            self.state = 598
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==14 or _la==94:
                self.state = 596
                self._errHandler.sync(self)
                token = self._input.LA(1)
                if token in [94]:
                    self.state = 591
                    self.match(EzLangParser.STRING_CONTENT)
                    pass
                elif token in [14]:
                    self.state = 592
                    self.match(EzLangParser.T__13)
                    self.state = 593
                    self.expression()
                    self.state = 594
                    self.match(EzLangParser.T__14)
                    pass
                else:
                    raise NoViableAltException(self)

                self.state = 600
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 601
            self.match(EzLangParser.T__12)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def SEMI(self):
            return self.getToken(EzLangParser.SEMI, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_expressionStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpressionStatement" ):
                listener.enterExpressionStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpressionStatement" ):
                listener.exitExpressionStatement(self)




    def expressionStatement(self):

        localctx = EzLangParser.ExpressionStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 108, self.RULE_expressionStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 603
            self.expression()
            self.state = 604
            self.match(EzLangParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def simpleType(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.SimpleTypeContext)
            else:
                return self.getTypedRuleContext(EzLangParser.SimpleTypeContext,i)


        def OR(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.OR)
            else:
                return self.getToken(EzLangParser.OR, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_type

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterType" ):
                listener.enterType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitType" ):
                listener.exitType(self)




    def type_(self):

        localctx = EzLangParser.TypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 110, self.RULE_type)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 606
            self.simpleType()
            self.state = 611
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,58,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 607
                    self.match(EzLangParser.OR)
                    self.state = 608
                    self.simpleType() 
                self.state = 613
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,58,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SimpleTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def baseType(self):
            return self.getTypedRuleContext(EzLangParser.BaseTypeContext,0)


        def typeSuffix(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.TypeSuffixContext)
            else:
                return self.getTypedRuleContext(EzLangParser.TypeSuffixContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_simpleType

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterSimpleType" ):
                listener.enterSimpleType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitSimpleType" ):
                listener.exitSimpleType(self)




    def simpleType(self):

        localctx = EzLangParser.SimpleTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 112, self.RULE_simpleType)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 614
            self.baseType()
            self.state = 618
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,59,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 615
                    self.typeSuffix() 
                self.state = 620
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,59,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeSuffixContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACK(self):
            return self.getToken(EzLangParser.LBRACK, 0)

        def RBRACK(self):
            return self.getToken(EzLangParser.RBRACK, 0)

        def INT(self):
            return self.getToken(EzLangParser.INT, 0)

        def QMARK(self):
            return self.getToken(EzLangParser.QMARK, 0)

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def simpleType(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.SimpleTypeContext)
            else:
                return self.getTypedRuleContext(EzLangParser.SimpleTypeContext,i)


        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def ARROW(self):
            return self.getToken(EzLangParser.ARROW, 0)

        def parameters(self):
            return self.getTypedRuleContext(EzLangParser.ParametersContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_typeSuffix

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterTypeSuffix" ):
                listener.enterTypeSuffix(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitTypeSuffix" ):
                listener.exitTypeSuffix(self)




    def typeSuffix(self):

        localctx = EzLangParser.TypeSuffixContext(self, self._ctx, self.state)
        self.enterRule(localctx, 114, self.RULE_typeSuffix)
        self._la = 0 # Token type
        try:
            self.state = 653
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [79]:
                self.enterOuterAlt(localctx, 1)
                self.state = 621
                self.match(EzLangParser.LBRACK)
                self.state = 623
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==88:
                    self.state = 622
                    self.match(EzLangParser.INT)


                self.state = 625
                self.match(EzLangParser.RBRACK)
                pass
            elif token in [72]:
                self.enterOuterAlt(localctx, 2)
                self.state = 626
                self.match(EzLangParser.QMARK)
                pass
            elif token in [67]:
                self.enterOuterAlt(localctx, 3)
                self.state = 627
                self.match(EzLangParser.LT)
                self.state = 628
                self.simpleType()
                self.state = 633
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==75:
                    self.state = 629
                    self.match(EzLangParser.COMMA)
                    self.state = 630
                    self.simpleType()
                    self.state = 635
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                self.state = 636
                self.match(EzLangParser.GT)
                pass
            elif token in [77]:
                self.enterOuterAlt(localctx, 4)
                self.state = 638
                self.match(EzLangParser.LPAREN)
                self.state = 640
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==87:
                    self.state = 639
                    self.parameters()


                self.state = 642
                self.match(EzLangParser.RPAREN)
                self.state = 643
                self.match(EzLangParser.ARROW)
                self.state = 644
                self.simpleType()
                pass
            elif token in [12]:
                self.enterOuterAlt(localctx, 5)
                self.state = 645
                self.match(EzLangParser.T__11)
                self.state = 646
                self.match(EzLangParser.LT)
                self.state = 647
                self.simpleType()
                self.state = 648
                self.match(EzLangParser.GT)
                self.state = 649
                self.match(EzLangParser.LBRACK)
                self.state = 650
                self.match(EzLangParser.INT)
                self.state = 651
                self.match(EzLangParser.RBRACK)
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


    class BaseTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_baseType

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBaseType" ):
                listener.enterBaseType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBaseType" ):
                listener.exitBaseType(self)




    def baseType(self):

        localctx = EzLangParser.BaseTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 116, self.RULE_baseType)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 655
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 134152192) != 0) or _la==87):
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


    class OptionalTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def QMARK(self):
            return self.getToken(EzLangParser.QMARK, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_optionalType

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterOptionalType" ):
                listener.enterOptionalType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitOptionalType" ):
                listener.exitOptionalType(self)




    def optionalType(self):

        localctx = EzLangParser.OptionalTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 118, self.RULE_optionalType)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 657
            self.type_()
            self.state = 658
            self.match(EzLangParser.QMARK)
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

        def type_(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.TypeContext)
            else:
                return self.getTypedRuleContext(EzLangParser.TypeContext,i)


        def OR(self):
            return self.getToken(EzLangParser.OR, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_unionType

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterUnionType" ):
                listener.enterUnionType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitUnionType" ):
                listener.exitUnionType(self)




    def unionType(self):

        localctx = EzLangParser.UnionTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 120, self.RULE_unionType)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 660
            self.type_()
            self.state = 661
            self.match(EzLangParser.OR)
            self.state = 662
            self.type_()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAREN(self):
            return self.getToken(EzLangParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(EzLangParser.RPAREN, 0)

        def ARROW(self):
            return self.getToken(EzLangParser.ARROW, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def parameters(self):
            return self.getTypedRuleContext(EzLangParser.ParametersContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_functionType

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunctionType" ):
                listener.enterFunctionType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunctionType" ):
                listener.exitFunctionType(self)




    def functionType(self):

        localctx = EzLangParser.FunctionTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 122, self.RULE_functionType)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 664
            self.match(EzLangParser.LPAREN)
            self.state = 666
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==87:
                self.state = 665
                self.parameters()


            self.state = 668
            self.match(EzLangParser.RPAREN)
            self.state = 669
            self.match(EzLangParser.ARROW)
            self.state = 670
            self.type_()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class GenericTypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def genericArgs(self):
            return self.getTypedRuleContext(EzLangParser.GenericArgsContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_genericType

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterGenericType" ):
                listener.enterGenericType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitGenericType" ):
                listener.exitGenericType(self)




    def genericType(self):

        localctx = EzLangParser.GenericTypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 124, self.RULE_genericType)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 672
            self.match(EzLangParser.ID)
            self.state = 673
            self.genericArgs()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class GenericArgsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def simpleType(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.SimpleTypeContext)
            else:
                return self.getTypedRuleContext(EzLangParser.SimpleTypeContext,i)


        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_genericArgs

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterGenericArgs" ):
                listener.enterGenericArgs(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitGenericArgs" ):
                listener.exitGenericArgs(self)




    def genericArgs(self):

        localctx = EzLangParser.GenericArgsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 126, self.RULE_genericArgs)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 675
            self.match(EzLangParser.LT)
            self.state = 676
            self.simpleType()
            self.state = 681
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==75:
                self.state = 677
                self.match(EzLangParser.COMMA)
                self.state = 678
                self.simpleType()
                self.state = 683
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 684
            self.match(EzLangParser.GT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class GenericParamsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LT(self):
            return self.getToken(EzLangParser.LT, 0)

        def ID(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.ID)
            else:
                return self.getToken(EzLangParser.ID, i)

        def GT(self):
            return self.getToken(EzLangParser.GT, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_genericParams

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterGenericParams" ):
                listener.enterGenericParams(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitGenericParams" ):
                listener.exitGenericParams(self)




    def genericParams(self):

        localctx = EzLangParser.GenericParamsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 128, self.RULE_genericParams)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 686
            self.match(EzLangParser.LT)
            self.state = 687
            self.match(EzLangParser.ID)
            self.state = 692
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==75:
                self.state = 688
                self.match(EzLangParser.COMMA)
                self.state = 689
                self.match(EzLangParser.ID)
                self.state = 694
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 695
            self.match(EzLangParser.GT)
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

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_decorator

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDecorator" ):
                listener.enterDecorator(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDecorator" ):
                listener.exitDecorator(self)




    def decorator(self):

        localctx = EzLangParser.DecoratorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 130, self.RULE_decorator)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 697
            self.match(EzLangParser.AT)
            self.state = 698
            self.match(EzLangParser.ID)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ControlStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def loopStatement(self):
            return self.getTypedRuleContext(EzLangParser.LoopStatementContext,0)


        def matchStatement(self):
            return self.getTypedRuleContext(EzLangParser.MatchStatementContext,0)


        def conditionalStatement(self):
            return self.getTypedRuleContext(EzLangParser.ConditionalStatementContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_controlStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterControlStatement" ):
                listener.enterControlStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitControlStatement" ):
                listener.exitControlStatement(self)




    def controlStatement(self):

        localctx = EzLangParser.ControlStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 132, self.RULE_controlStatement)
        try:
            self.state = 703
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [33]:
                self.enterOuterAlt(localctx, 1)
                self.state = 700
                self.loopStatement()
                pass
            elif token in [41]:
                self.enterOuterAlt(localctx, 2)
                self.state = 701
                self.matchStatement()
                pass
            elif token in [11, 12, 34, 42, 43, 44, 47, 48, 52, 53, 64, 67, 77, 87, 88, 89, 90]:
                self.enterOuterAlt(localctx, 3)
                self.state = 702
                self.conditionalStatement()
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


    class LoopStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LOOP(self):
            return self.getToken(EzLangParser.LOOP, 0)

        def rangeLoop(self):
            return self.getTypedRuleContext(EzLangParser.RangeLoopContext,0)


        def infiniteLoop(self):
            return self.getTypedRuleContext(EzLangParser.InfiniteLoopContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_loopStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLoopStatement" ):
                listener.enterLoopStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLoopStatement" ):
                listener.exitLoopStatement(self)




    def loopStatement(self):

        localctx = EzLangParser.LoopStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 134, self.RULE_loopStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 705
            self.match(EzLangParser.LOOP)
            self.state = 708
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [87]:
                self.state = 706
                self.rangeLoop()
                pass
            elif token in [81]:
                self.state = 707
                self.infiniteLoop()
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


    class InfiniteLoopContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_infiniteLoop

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInfiniteLoop" ):
                listener.enterInfiniteLoop(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInfiniteLoop" ):
                listener.exitInfiniteLoop(self)




    def infiniteLoop(self):

        localctx = EzLangParser.InfiniteLoopContext(self, self._ctx, self.state)
        self.enterRule(localctx, 136, self.RULE_infiniteLoop)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 710
            self.block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RangeLoopContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def IN(self):
            return self.getToken(EzLangParser.IN, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def ELLIPSIS(self):
            return self.getToken(EzLangParser.ELLIPSIS, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_rangeLoop

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRangeLoop" ):
                listener.enterRangeLoop(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRangeLoop" ):
                listener.exitRangeLoop(self)




    def rangeLoop(self):

        localctx = EzLangParser.RangeLoopContext(self, self._ctx, self.state)
        self.enterRule(localctx, 138, self.RULE_rangeLoop)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 712
            self.match(EzLangParser.ID)
            self.state = 713
            self.match(EzLangParser.IN)
            self.state = 714
            self.expression()
            self.state = 715
            self.match(EzLangParser.ELLIPSIS)
            self.state = 716
            self.expression()
            self.state = 717
            self.block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ConditionalStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ExpressionContext,i)


        def QMARK(self):
            return self.getToken(EzLangParser.QMARK, 0)

        def block(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.BlockContext)
            else:
                return self.getTypedRuleContext(EzLangParser.BlockContext,i)


        def COLON(self):
            return self.getToken(EzLangParser.COLON, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_conditionalStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterConditionalStatement" ):
                listener.enterConditionalStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitConditionalStatement" ):
                listener.exitConditionalStatement(self)




    def conditionalStatement(self):

        localctx = EzLangParser.ConditionalStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 140, self.RULE_conditionalStatement)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 719
            self.expression()
            self.state = 720
            self.match(EzLangParser.QMARK)
            self.state = 723
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [11, 12, 34, 42, 43, 44, 47, 48, 52, 53, 64, 67, 77, 87, 88, 89, 90]:
                self.state = 721
                self.expression()
                pass
            elif token in [81]:
                self.state = 722
                self.block()
                pass
            else:
                raise NoViableAltException(self)

            self.state = 730
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==73:
                self.state = 725
                self.match(EzLangParser.COLON)
                self.state = 728
                self._errHandler.sync(self)
                token = self._input.LA(1)
                if token in [11, 12, 34, 42, 43, 44, 47, 48, 52, 53, 64, 67, 77, 87, 88, 89, 90]:
                    self.state = 726
                    self.expression()
                    pass
                elif token in [81]:
                    self.state = 727
                    self.block()
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


    class MatchStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def MATCH(self):
            return self.getToken(EzLangParser.MATCH, 0)

        def LBRACE(self):
            return self.getToken(EzLangParser.LBRACE, 0)

        def matchCase(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.MatchCaseContext)
            else:
                return self.getTypedRuleContext(EzLangParser.MatchCaseContext,i)


        def RBRACE(self):
            return self.getToken(EzLangParser.RBRACE, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(EzLangParser.COMMA)
            else:
                return self.getToken(EzLangParser.COMMA, i)

        def getRuleIndex(self):
            return EzLangParser.RULE_matchStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMatchStatement" ):
                listener.enterMatchStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMatchStatement" ):
                listener.exitMatchStatement(self)




    def matchStatement(self):

        localctx = EzLangParser.MatchStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 142, self.RULE_matchStatement)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 732
            self.match(EzLangParser.MATCH)
            self.state = 733
            self.match(EzLangParser.LBRACE)
            self.state = 734
            self.matchCase()
            self.state = 739
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==75:
                self.state = 735
                self.match(EzLangParser.COMMA)
                self.state = 736
                self.matchCase()
                self.state = 741
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 742
            self.match(EzLangParser.RBRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MatchCaseContext(ParserRuleContext):
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

        def QMARK(self):
            return self.getToken(EzLangParser.QMARK, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_matchCase

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMatchCase" ):
                listener.enterMatchCase(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMatchCase" ):
                listener.exitMatchCase(self)




    def matchCase(self):

        localctx = EzLangParser.MatchCaseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 144, self.RULE_matchCase)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 744
            self.match(EzLangParser.LPAREN)
            self.state = 745
            self.expression()
            self.state = 746
            self.match(EzLangParser.RPAREN)
            self.state = 747
            self.match(EzLangParser.QMARK)
            self.state = 750
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [11, 12, 34, 42, 43, 44, 47, 48, 52, 53, 64, 67, 77, 87, 88, 89, 90]:
                self.state = 748
                self.expression()
                pass
            elif token in [81]:
                self.state = 749
                self.block()
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





