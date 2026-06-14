REPORT zhello_test.

CLASS zcl_greeter DEFINITION.
  PUBLIC SECTION.
    METHODS greet
      IMPORTING iv_name TYPE string.
    METHODS get_message
      RETURNING VALUE(rv_msg) TYPE string.
ENDCLASS.

CLASS zcl_greeter IMPLEMENTATION.
  METHOD greet.
    CALL FUNCTION 'SUSR_USER_CHANGE_PASSWORD_RFC'
      EXPORTING
        bname = iv_name.
    PERFORM format_output.
  ENDMETHOD.

  METHOD get_message.
    rv_msg = 'Hello'.
    ZCL_HELPER=>log( iv_msg = rv_msg ).
  ENDMETHOD.
ENDCLASS.

INTERFACE zif_printable.
  METHODS print.
ENDINTERFACE.

FORM format_output.
  WRITE: / 'formatted'.
ENDFORM.
