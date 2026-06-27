CLASS zcl_raiser DEFINITION PUBLIC FINAL.
  PUBLIC SECTION.
    METHODS raise_type.
    METHODS raise_type_exporting.
    METHODS raise_new.
ENDCLASS.

CLASS zcl_raiser IMPLEMENTATION.

  METHOD raise_type.
    RAISE EXCEPTION TYPE zcx_vale_error.
  ENDMETHOD.

  METHOD raise_type_exporting.
    RAISE EXCEPTION TYPE zcx_vale_error
      EXPORTING
        textid = zcx_vale_error=>error_text.
  ENDMETHOD.

  METHOD raise_new.
    RAISE EXCEPTION NEW zcx_vale_error( ).
  ENDMETHOD.

ENDCLASS.
