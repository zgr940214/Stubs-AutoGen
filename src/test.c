#include "test.h"
typedef struct
{
    int a;
} very_hard_one;

static very_hard_one global; 


int test1(void) {
    
    int ret = 0;
    int pp1, pp2;
    char* pt1, pt2;

    ret = external_func1(global, pp1, pt1);

    ret = external_function2(1, "test", "example");
    
    return ret;
};

int test2(int a) {
    test1();

    external_func3(a, a + 1);

    return 0;
};