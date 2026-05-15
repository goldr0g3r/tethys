/*
 * test_scaffold_smoke.c - placeholder Unity test proving the Ceedling
 * scaffold compiles and runs.
 *
 * This test exists ONLY to keep the test build green from PR-1a onward.
 * It will be deleted at the first Phase-1+ PR that introduces real test
 * coverage of slave/src/core/.
 *
 * Cite: parent plan section 6.7 (CI gate matrix - unit tests).
 * Trace: parent plan section 14 (repository layout - slave/tests/).
 */

#include "unity.h"

void setUp(void)
{
    /* No-op fixture. */
}

void tearDown(void)
{
    /* No-op fixture. */
}

void test_scaffold_smoke_arithmetic(void)
{
    TEST_ASSERT_EQUAL_INT(4, 2 + 2);
}

void test_scaffold_smoke_unity_macros(void)
{
    TEST_ASSERT_TRUE(1);
    TEST_ASSERT_FALSE(0);
    TEST_ASSERT_NOT_NULL("non-null");
}
