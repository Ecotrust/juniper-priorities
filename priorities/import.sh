DATA_DIR=/usr/local/apps/madrona-priorities/priorities/data/data_04092013
python manage.py import_planning_units \
    $DATA_DIR/PUfinal_prjsmpl.shp \
    $DATA_DIR/BLM_metrics20130503.xls \
    $DATA_DIR/PU_Finalprj.shp

