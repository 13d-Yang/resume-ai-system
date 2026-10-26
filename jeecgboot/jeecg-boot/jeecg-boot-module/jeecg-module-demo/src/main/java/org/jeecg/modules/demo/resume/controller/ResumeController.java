package org.jeecg.modules.demo.resume.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.resume.entity.Resume;
import org.jeecg.modules.demo.resume.service.IResumeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.File;
import java.net.URLEncoder;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/resume")
@CrossOrigin(origins = "*", allowedHeaders = "*", methods = {RequestMethod.POST, RequestMethod.GET, RequestMethod.DELETE})
public class ResumeController {

	@Autowired
	private IResumeService resumeService;
	private static final String SOURCE_DIR = "C:\\Users\\简历测试数据";
	private static final String STORAGE_DIR = "C:\\Users\\简历测试数据\\存储\\";

	// ===================== 普通上传 =====================
	@PostMapping("/upload")
	public Result<?> upload(@RequestParam("file") MultipartFile file) {
		try {
			String originalFilename = file.getOriginalFilename();
			String suffix = originalFilename.substring(originalFilename.lastIndexOf("."));
			String uuidFileName = UUID.randomUUID() + suffix;

			File dir = new File(STORAGE_DIR);
			if (!dir.exists()) dir.mkdirs();

			File targetFile = new File(STORAGE_DIR + uuidFileName);
			file.transferTo(targetFile);

			Resume resume = new Resume();
			resume.setResumeName(originalFilename.replace(suffix, ""));
			resume.setResumeFile(originalFilename);
			resume.setResumePath(STORAGE_DIR + uuidFileName);
			resume.setCreateTime(new Date());
			resume.setUpdateTime(new Date());
			resume.setDelFlag(0);
			resume.setStatus(2);

			resumeService.save(resume);
			return Result.OK("上传成功！");
		} catch (Exception e) {
			e.printStackTrace();
			return Result.error("上传失败：" + e.getMessage());
		}
	}

	// ===================== 从源目录同步单个文件 =====================
	@PostMapping("/sync-single-file")
	public Result<?> syncSingleFile(@RequestParam("fileName") String fileName) {
		try {
			File sourceFile = new File(SOURCE_DIR, fileName);
			if (!sourceFile.exists()) return Result.error("文件不存在：" + fileName);

			File storageDir = new File(STORAGE_DIR);
			if (!storageDir.exists()) storageDir.mkdirs();

			String suffix = fileName.substring(fileName.lastIndexOf("."));
			String newFileName = UUID.randomUUID() + suffix;
			File targetFile = new File(storageDir, newFileName);

			Files.copy(sourceFile.toPath(), targetFile.toPath(), StandardCopyOption.REPLACE_EXISTING);

			Resume resume = new Resume();
			resume.setResumeName(fileName.replace(suffix, ""));
			resume.setResumeFile(fileName);
			resume.setResumePath(targetFile.getAbsolutePath());
			resume.setCreateTime(new Date());
			resume.setUpdateTime(new Date());
			resume.setDelFlag(0);
			resume.setStatus(2);

			resumeService.save(resume);
			return Result.OK("文件同步成功：" + fileName);
		} catch (Exception e) {
			e.printStackTrace();
			return Result.error("同步失败：" + e.getMessage());
		}
	}

	// ===================== 【修复】读取源目录只显示 PDF/DOC/DOCX =====================
	@GetMapping("/listSourceFiles")
	public Result<?> listSourceFiles() {
		File dir = new File(SOURCE_DIR);
		if (!dir.exists()) return Result.error("目录不存在");

		File[] files = dir.listFiles();
		if (files == null) return Result.error("无文件");

		List<String> list = new ArrayList<>();
		for (File f : files) {
			if (f.isFile()) {
				String name = f.getName().toLowerCase();
				if (name.endsWith(".pdf") || name.endsWith(".doc") || name.endsWith(".docx")) {
					list.add(f.getName());
				}
			}
		}
		return Result.OK(list);
	}

	// ===================== 【修复】下载：真实格式、不损坏、可打开 =====================
	@GetMapping("/download")
	public void download(@RequestParam("id") Long id, HttpServletResponse response) {
		try {
			Resume resume = resumeService.getById(id);
			if (resume == null) {
				response.sendError(HttpServletResponse.SC_NOT_FOUND);
				return;
			}

			File file = new File(resume.getResumePath());
			if (!file.exists()) {
				response.sendError(HttpServletResponse.SC_NOT_FOUND);
				return;
			}

			// 自动获取真实后缀
			String fileName = resume.getResumeName();
			String filePath = resume.getResumePath();
			String suffix = filePath.substring(filePath.lastIndexOf("."));
			String downName = fileName + suffix;

			// 自动设置MIME类型
			String contentType = Files.probeContentType(file.toPath());
			if (contentType == null) contentType = "application/octet-stream";

			response.setContentType(contentType);
			response.setHeader("Content-Disposition", "attachment;filename=" + URLEncoder.encode(downName, "UTF-8"));
			response.setHeader("Content-Length", String.valueOf(file.length()));

			Files.copy(file.toPath(), response.getOutputStream());
			response.getOutputStream().flush();
		} catch (Exception e) {
			e.printStackTrace();
		}
	}

	// ===================== 列表、删除、编辑、统计（不动） =====================

	@GetMapping(value = "/list")
	public Result<IPage<Resume>> list(
			Resume resume,
			@RequestParam(name="pageNo", defaultValue="1") Integer pageNo,
			@RequestParam(name="pageSize", defaultValue="10") Integer pageSize,
			HttpServletRequest req) {

		QueryWrapper<Resume> queryWrapper = new QueryWrapper<>();
		queryWrapper.eq("del_flag", 0);
		queryWrapper.orderByDesc("create_time");

		Page<Resume> page = new Page<>(pageNo, pageSize);
		IPage<Resume> pageList = resumeService.page(page, queryWrapper);
		return Result.OK(pageList);
	}

	@DeleteMapping("/delete")
	public Result<?> delete(@RequestParam(name = "id") String id) {
		Resume resume = resumeService.getById(id);
		if (resume == null) return Result.error("数据不存在");

		try {
			File file = new File(resume.getResumePath());
			if (file.exists()) file.delete();
		} catch (Exception e) {
			e.printStackTrace();
		}

		resumeService.removeById(id);
		return Result.OK("删除成功");
	}

	@DeleteMapping("/deleteBatch")
	public Result<?> deleteBatch(@RequestParam(name = "ids") String ids) {
		String[] idArr = ids.split(",");
		for (String id : idArr) {
			Resume resume = resumeService.getById(id);
			if (resume != null) {
				try {
					File file = new File(resume.getResumePath());
					if (file.exists()) file.delete();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
		}
		resumeService.removeByIds(Arrays.asList(idArr));
		return Result.OK("批量删除成功");
	}

	@PutMapping("/edit")
	public Result<?> edit(@RequestBody Resume resume){
		resumeService.updateById(resume);
		return Result.OK("修改成功");
	}

	@GetMapping("/getResumeStats")
	public Result<Map<String, Long>> getResumeStats() {
		QueryWrapper<Resume> allWrapper = new QueryWrapper<>();
		allWrapper.eq("del_flag", 0);
		Long totalAll = resumeService.count(allWrapper);

		QueryWrapper<Resume> waitWrapper = new QueryWrapper<>();
		waitWrapper.eq("del_flag", 0).eq("status", 2);
		Long waitFilter = resumeService.count(waitWrapper);

		QueryWrapper<Resume> interviewWrapper = new QueryWrapper<>();
		interviewWrapper.eq("del_flag", 0).eq("status", 1);
		Long interviewing = resumeService.count(interviewWrapper);

		QueryWrapper<Resume> employWrapper = new QueryWrapper<>();
		employWrapper.eq("del_flag", 0).eq("status", 3);
		Long employed = resumeService.count(employWrapper);

		// 👇👇👇 只在这里加了 已拒绝 统计
		QueryWrapper<Resume> rejectWrapper = new QueryWrapper<>();
		rejectWrapper.eq("del_flag", 0).eq("status", 4);
		Long rejected = resumeService.count(rejectWrapper);

		Map<String, Long> map = new HashMap<>();
		map.put("totalAll", totalAll);
		map.put("waitFilter", waitFilter);
		map.put("interviewing", interviewing);
		map.put("employed", employed);
		map.put("rejected", rejected); // 👈 只加了这一行
		return Result.OK(map);
	}
}