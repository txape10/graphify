CLASS zcl_factory DEFINITION.
  PUBLIC SECTION.
    METHODS create_all.
ENDCLASS.

CLASS zcl_factory IMPLEMENTATION.
  METHOD create_all.
    DATA lo_ref    TYPE REF TO zcl_product.
    DATA(lo_new)  = NEW zcl_product( ).
    CREATE OBJECT lo_ref TYPE zcl_product.
  ENDMETHOD.
ENDCLASS.
