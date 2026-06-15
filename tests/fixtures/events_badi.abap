CLASS zcl_button DEFINITION PUBLIC.
  PUBLIC SECTION.
    EVENTS button_clicked EXPORTING VALUE(iv_id) TYPE i.
    CLASS-EVENTS class_initialized.
    METHODS click.
ENDCLASS.

CLASS zcl_handler DEFINITION PUBLIC.
  PUBLIC SECTION.
    METHODS on_click FOR EVENT button_clicked OF zcl_button
      IMPORTING iv_id.
ENDCLASS.

CLASS zcl_button IMPLEMENTATION.
  METHOD click.
    RAISE EVENT button_clicked EXPORTING iv_id = 1.
  ENDMETHOD.
ENDCLASS.

CLASS zcl_handler IMPLEMENTATION.
  METHOD on_click.
    DATA lo_btn TYPE REF TO zcl_button.
    CREATE OBJECT lo_btn.
    SET HANDLER me->on_click FOR lo_btn.
  ENDMETHOD.
ENDCLASS.

CLASS zcl_report DEFINITION PUBLIC.
  PUBLIC SECTION.
    METHODS run.
ENDCLASS.

CLASS zcl_report IMPLEMENTATION.
  METHOD run.
    DATA lo_badi TYPE REF TO zif_ex_my_badi.
    GET BADI lo_badi TYPE zif_ex_my_badi.
    CALL BADI lo_badi->execute
      EXPORTING iv_param = 'X'.
  ENDMETHOD.
ENDCLASS.
