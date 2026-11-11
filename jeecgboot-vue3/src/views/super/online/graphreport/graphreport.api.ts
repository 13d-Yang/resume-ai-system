import { defHttp } from '/@/utils/http/axios';

export enum Api {
  list = '/online/graphreport/head/list',
  delete = '/online/graphreport/head/delete',
  deleteBatch = '/online/graphreport/head/deleteBatch',
  exportXls = '/online/graphreport/head/exportXls',
  importXls = '/online/graphreport/head/importExcel',
  parseField = '/online/graphreport/head/parseField',
  paramsList = '/online/graphreport/params/listByHeadId',
  getChartsData = '/online/graphreport/api/getChartsData',
  getParamsInfo = '/online/graphreport/params/listByHeadId',
}

/**
 * 列表接口
 * e3e3NcxzbUiGa53YYVXxWc8ADo5ISgQGx/gaZwERF91oAryDlivjqBv3wqRArgChupi+Y/Gg/swwGEyL0PuVFg==
 * @param params
 */
export const list = (params) => defHttp.get({ url: Api.list, params });

// 批量删除
export function doBatchDelete(idList: string[]) {
  return defHttp.delete(
    {
      url: Api.deleteBatch,
      params: { ids: idList.join(',') },
    },
    { joinParamsToUrl: true }
  );
}

export const queryParamsList = (headId: string) => defHttp.get({ url: Api.paramsList, params: { headId } });

// 查询图表数据
export const getChartsData = (params) => defHttp.get({ url: Api.getChartsData, params: params });
export const getParamsInfo = (params) => defHttp.get({ url: Api.getParamsInfo, params: params });

export const parseField = (type, data, params = {}) => defHttp.post({ url: Api.parseField, params: { type, data, ...params } });
