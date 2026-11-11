package org.jeecg.modules.demo.resume.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.resume.entity.Resume;
import org.jeecg.modules.demo.resume.service.IResumeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import jakarta.servlet.http.HttpServletResponse;
import java.io.File;
import java.net.URLEncoder;
import java.nio.file.Files;

@RestController
@RequestMapping("/resume")
@CrossOrigin(origins = "*", allowedHeaders = "*", methods = {RequestMethod.POST, RequestMethod.GET, RequestMethod.DELETE})
public class ResumeController {

	@Autowired
	private IResumeService resumeService;

	// ===================== 普通上传 =====================
	@PostMapping("/upload")
	public Result<?> upload(@RequestParam("file") MultipartFile file) {
		try {
			resumeService.upload(file);
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
			resumeService.syncSingleFile(fileName);
			return Result.OK("文件同步成功：" + fileName);
		} catch (IllegalArgumentException e) {
			return Result.error(e.getMessage());
		} catch (Exception e) {
			e.printStackTrace();
			return Result.error("同步失败：" + e.getMessage());
		}
	}

	// ===================== 读取源目录只显示 PDF/DOC/DOCX =====================
	@GetMapping("/listSourceFiles")
	public Result<?> listSourceFiles() {
		try {
			return Result.OK(resumeService.listSourceFiles());
		} catch (Exception e) {
			return Result.error(e.getMessage());
		}
	}

	// ===================== 下载：真实格式、不损坏、可打开 =====================
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

	// ===================== 列表、删除、编辑、统计 =====================

	@GetMapping(value = "/list")
	public Result<IPage<Resume>> list(
			@RequestParam(name="pageNo", defaultValue="1") Integer pageNo,
			@RequestParam(name="pageSize", defaultValue="10") Integer pageSize) {
		return Result.OK(resumeService.pageList(pageNo, pageSize));
	}

	@DeleteMapping("/delete")
	public Result<?> delete(@RequestParam(name = "id") String id) {
		try {
			resumeService.deleteResume(id);
			return Result.OK("删除成功");
		} catch (IllegalArgumentException e) {
			return Result.error(e.getMessage());
		}
	}

	@DeleteMapping("/deleteBatch")
	public Result<?> deleteBatch(@RequestParam(name = "ids") String ids) {
		try {
			resumeService.deleteBatchResumes(ids);
			return Result.OK("批量删除成功");
		} catch (Exception e) {
			e.printStackTrace();
			return Result.error("批量删除失败：" + e.getMessage());
		}
	}

	@PutMapping("/edit")
	public Result<?> edit(@RequestBody Resume resume){
		resumeService.updateById(resume);
		return Result.OK("修改成功");
	}

	@GetMapping("/getResumeStats")
	public Result<?> getResumeStats() {
		return Result.OK(resumeService.getStats());
	}
}
