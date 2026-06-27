REPORT zmethod_call_test.

CLASS zcl_caller DEFINITION.
  PUBLIC SECTION.
    METHODS run.
ENDCLASS.

CLASS zcl_caller IMPLEMENTATION.
  METHOD run.
    DATA lo_bar TYPE REF TO zcl_target_instance.
    " Static call: Bug 1 (no edge) + Bug 2 (no uses to class)
    zcl_target_static=>compute( iv_val = 42 ).
    " Instance call through typed variable: Bug 1
    lo_bar->process( ).
    " Untyped variable: must be silently ignored
    lo_unknown->anything( ).
  ENDMETHOD.
ENDCLASS.
