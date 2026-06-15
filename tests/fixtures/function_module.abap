FUNCTION-POOL zfm_test.

FUNCTION z_add_numbers.
  IMPORTING
    iv_a TYPE i
    iv_b TYPE i
  EXPORTING
    ev_result TYPE i.

  ev_result = iv_a + iv_b.
ENDFUNCTION.

FUNCTION z_caller.
  DATA lv_res TYPE i.

  CALL FUNCTION 'Z_ADD_NUMBERS'
    EXPORTING
      iv_a     = 1
      iv_b     = 2
    IMPORTING
      ev_result = lv_res.
ENDFUNCTION.
