CLASS zcl_sql_demo DEFINITION PUBLIC.
  PUBLIC SECTION.
    METHODS read_log.
    METHODS save_log IMPORTING is_h TYPE ztest_log_h it_m TYPE STANDARD TABLE.
    METHODS clean_up.
    METHODS negatives.
  PRIVATE SECTION.
    DATA tab_local TYPE STANDARD TABLE OF ztest_log_m.
    DATA mi_buffer TYPE STANDARD TABLE OF ztest_log_m.
ENDCLASS.

CLASS zcl_sql_demo IMPLEMENTATION.

  METHOD read_log.
    SELECT SINGLE FROM lfa1 FIELDS ktokk WHERE lifnr EQ @lv_x INTO @DATA(lv_k).
    SELECT vbeln, posnr FROM ztest_log_h INNER JOIN vbap ON vbap~vbeln = ztest_log_h~vbeln INTO TABLE @DATA(lt_a).
    SELECT SINGLE
      FROM ztest_log_m
      FIELDS *
      WHERE vbeln = @lv_v
      INTO @DATA(ls_m).
    SELECT FROM ztest_log_r AS t_r
      INNER JOIN ztest_log_e AS t_e
        ON t_e~vbeln = t_r~vbeln
      FIELDS t_r~vbeln
      WHERE t_r~vbeln IN ( SELECT vbeln FROM ztest_log_sub )
      INTO TABLE @DATA(lt_b).
* Leer datos. Fin del comentario
    SELECT * FROM nast
      INTO TABLE lt_nast
      WHERE kappl = 'V1'.
  ENDMETHOD.

  METHOD save_log.
    MODIFY ztest_log_h FROM is_h.
    MODIFY ztest_log_m FROM TABLE it_m.
    UPDATE ztest_log_h SET erdat = sy-datum WHERE vbeln = lv_v.
    UPDATE ztest_log_r FROM TABLE lt_r[].
    INSERT ztest_log_e FROM TABLE it_e.
    INSERT INTO ztest_log_x VALUES ls_x.
    INSERT ztest_log_cl CLIENT SPECIFIED FROM TABLE it_cl.
    MODIFY ztest_log_cm CLIENT SPECIFIED FROM ls_cm.
  ENDMETHOD.

  METHOD clean_up.
    DELETE FROM ztest_log_x WHERE vbeln = lv_v.
    DELETE ztest_log_r FROM TABLE it_r.
    DELETE ztest_log_t FROM is_t.
    DELETE: ztest_log_c FROM TABLE it_c, ztest_log_d FROM TABLE it_d.
  ENDMETHOD.

  METHOD negatives.
    DELETE lt_tab INDEX 1.
    DELETE ADJACENT DUPLICATES FROM lt_tab.
    SELECT vbeln FROM @lt_data AS t_data INTO TABLE @DATA(lt_x).
    SELECT a~vbeln FROM ztest_log_h AS a INNER JOIN @it_ret AS b ON b~vbeln = a~vbeln INTO TABLE @lt_y.
    SELECT vbeln FROM (lv_dyn) INTO TABLE @lt_z.
* SELECT * FROM zcomment_col1.
    " SELECT * FROM zcomment_quote.
    lv_text = 'SELECT * FROM zliteral'.
    lv_text = |SELECT * FROM ztemplate|.
    MODIFY ls_decl FROM ls_y.
    MODIFY lt_local FROM ls_y.
    MODIFY mi_buffer FROM ls_y.
    MODIFY tab_local FROM ls_y.
    INSERT INTO TABLE lt_ins FROM ls_y.
    SELECT-OPTIONS: so_x FOR lv_x.
    lv_val = ls_p-from.
    lv_val = lv_period-from.
  ENDMETHOD.

ENDCLASS.

FORM top_form.
  DELETE FROM ztest_form_tab WHERE mandt = sy-mandt.
ENDFORM.

MODIFY ztest_toplevel FROM TABLE gt_top.
